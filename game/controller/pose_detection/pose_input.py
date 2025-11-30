from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

import cv2
import mediapipe as mp

@dataclass
class PoseReading:
    """Snapshot of a single pose sample, including metadata needed by the game."""
    state: PoseState
    slope: float
    confidence: float
    landmarks: Any | None

class PoseState(str, Enum):
    NO_POSE = "no_pose"
    T_POSE = "t_pose"
    HANDS_UP = "hands_up"
    HANDS_DOWN = "hands_down"

class PoseController:
    """Wraps MediaPipe Pose and exposes discrete pose states plus a turning slope."""

    def __init__(self, camera_index: int = 0, mirror: bool = True) -> None:
        """Configure camera capture and prepare MediaPipe pose estimation."""

        self.camera_index = camera_index
        self.mirror = mirror
        self.available = bool(cv2 and mp)
        self._pose = None
        self._cap = None
        self._last_state = PoseState.NO_POSE
        self._last_slope = 0.0
        self._last_confidence = 0.0
        self._last_frame: Optional[Any] = None  # Raw BGR frame from OpenCV
        self._last_landmarks = None
        if self.available:
            self._boot_hardware()

    def _boot_hardware(self) -> None:
        """Allocate the OpenCV capture and MediaPipe pose graph."""

        self._cap = cv2.VideoCapture(self.camera_index)
        if not self._cap.isOpened():
            self.available = False
            return
        mp_pose = mp.solutions.pose
        self._pose = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)

    def read(self) -> Optional[PoseState]:
        """Grab a frame, infer pose landmarks, and update cached metrics."""

        if not self.available or self._cap is None or self._pose is None:
            return None

        ok, frame = self._cap.read()
        if not ok:
            self._last_state = PoseState.NO_POSE
            self._last_slope = 0.0
            self._last_confidence = 0.0
            self._last_landmarks = None
            return None
        if self.mirror:
            frame = cv2.flip(frame, 1)
        self._last_frame = frame.copy()
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        results = self._pose.process(rgb)
        if not results.pose_landmarks:
            self._last_state = PoseState.NO_POSE
            self._last_slope = 0.0
            self._last_confidence = 0.0
            self._last_landmarks = None
            return None

        landmarks = results.pose_landmarks.landmark
        self._last_confidence = self._compute_confidence(landmarks)
        self._last_landmarks = results.pose_landmarks
        self._last_state = self._classify_state(landmarks)
        return self._last_state

    def _classify_state_metrics(self, landmarks) -> tuple[PoseState, float]:
        """Return the inferred pose state and slope given landmark inputs."""

        mp_pose = mp.solutions.pose
        left_shoulder = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER]
        right_shoulder = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER]
        left_wrist = landmarks[mp_pose.PoseLandmark.LEFT_WRIST]
        right_wrist = landmarks[mp_pose.PoseLandmark.RIGHT_WRIST]
        slope = 0.0

        left_wrist_vis = getattr(left_wrist, "visibility", 1.0)
        right_wrist_vis = getattr(right_wrist, "visibility", 1.0)
        min_wrist_visibility = min(left_wrist_vis, right_wrist_vis)
        visibility_threshold = 0.45
        if min_wrist_visibility < visibility_threshold:
            return PoseState.NO_POSE, 0.0

        dx = right_wrist.x - left_wrist.x
        if abs(dx) < 1e-5:
            dx = 1e-5 if dx >= 0 else -1e-5
        slope = (right_wrist.y - left_wrist.y) / dx

        avg_shoulder_y = (left_shoulder.y + right_shoulder.y) / 2
        up_margin = 0.05
        down_margin = 0.05

        if left_wrist.y < avg_shoulder_y - up_margin and right_wrist.y < avg_shoulder_y - up_margin:
            return PoseState.HANDS_UP, slope

        if left_wrist.y > avg_shoulder_y + down_margin and right_wrist.y > avg_shoulder_y + down_margin:
            return PoseState.HANDS_DOWN, slope

        shoulder_span = max(abs(right_shoulder.x - left_shoulder.x), 1e-5)
        wrist_span = abs(right_wrist.x - left_wrist.x)
        arms_extended = wrist_span >= shoulder_span * 0.6

        alignment_tolerance = 0.1
        left_inline = abs(left_wrist.y - left_shoulder.y) <= alignment_tolerance
        right_inline = abs(right_wrist.y - right_shoulder.y) <= alignment_tolerance
        if left_inline and right_inline or arms_extended:
            return PoseState.T_POSE, slope

        return PoseState.NO_POSE, slope

    def _classify_state(self, landmarks) -> PoseState:
        """Persist slope state while returning the latest PoseState."""

        state, slope = self._classify_state_metrics(landmarks)
        self._last_slope = slope
        return state

    def _compute_confidence(self, landmarks) -> float:
        """Estimate confidence based on key landmark visibility."""

        mp_pose = mp.solutions.pose
        key_points = [
            landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER],
            landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER],
            landmarks[mp_pose.PoseLandmark.LEFT_WRIST],
            landmarks[mp_pose.PoseLandmark.RIGHT_WRIST],
        ]
        visibilities = [getattr(point, "visibility", 0.0) for point in key_points]
        avg_visibility = sum(visibilities) / len(visibilities)
        return max(0.0, min(1.0, avg_visibility))

    @property
    def state(self) -> PoseState:
        """Return the last classified pose state."""

        return self._last_state or PoseState.NO_POSE

    @property
    def frame(self):
        """Expose the latest captured BGR frame for overlays."""

        return self._last_frame

    @property
    def landmarks(self):
        """Expose MediaPipe's latest landmark packet, if present."""

        return self._last_landmarks
    
    @property
    def turn_slope(self) -> float:
        """Return the horizontal slope derived from wrist offsets."""

        return self._last_slope

    @property
    def confidence(self) -> float:
        """Return the most recent average visibility score."""

        return self._last_confidence

    def shutdown(self) -> None:
        """Release camera resources and destroy pose estimators."""

        if self._cap is not None:
            self._cap.release()
            self._cap = None
        if self._pose is not None:
            self._pose.close()
            self._pose = None

    def __del__(self) -> None:
        """Ensure hardware resources are released on garbage collection."""

        self.shutdown()


class DualPoseController(PoseController):
    """Prototype controller that splits the camera feed for two independent poses."""

    def __init__(self, camera_index: int = 0, mirror: bool = True) -> None:
        """Initialize two MediaPipe pose models fed by the same camera."""

        super().__init__(camera_index=camera_index, mirror=mirror)
        self._pair: tuple[PoseReading | None, PoseReading | None] = (None, None)
        self._pose_models: tuple[Any | None, Any | None] | None = None
        if self.available and mp is not None:
            # Replace single-pose graph with two independent ones (one per region).
            if self._pose is not None:
                self._pose.close()
                self._pose = None
            mp_pose = mp.solutions.pose
            pose_kwargs = dict(min_detection_confidence=0.5, min_tracking_confidence=0.5)
            self._pose_models = (mp_pose.Pose(**pose_kwargs), mp_pose.Pose(**pose_kwargs))

    def read_pair(self) -> tuple[PoseReading | None, PoseReading | None]:
        """Return the latest left/right pose readings (or None placeholders)."""
        if not self.available or self._cap is None or not self._pose_models:
            self._pair = (None, None)
            return self._pair

        ok, frame = self._cap.read()
        if not ok:
            self._pair = (None, None)
            return self._pair
        if self.mirror:
            frame = cv2.flip(frame, 1)
        self._last_frame = frame.copy()

        h, w = frame.shape[:2]
        mid = w // 2
        left_frame = frame[:, :mid]
        right_frame = frame[:, mid:]
        left_pose = self._pose_models[0]
        right_pose = self._pose_models[1]

        left = self._process_region(left_frame, left_pose, 0, mid, w, h)
        right = self._process_region(right_frame, right_pose, mid, w - mid, w, h)
        self._pair = (left, right)
        return self._pair

    def _process_region(
        self,
        frame,
        pose_model,
        x_offset: int,
        region_width: int,
        full_width: int,
        full_height: int,
    ) -> PoseReading | None:
        """Run pose estimation on a cropped region and report pose classification metrics."""
        if frame is None or pose_model is None or region_width <= 0 or full_width <= 0 or full_height <= 0:
            return None

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        results = pose_model.process(rgb)
        if not results.pose_landmarks:
            return None

        landmarks = results.pose_landmarks.landmark
        state, slope = self._classify_state_metrics(landmarks)

        return PoseReading(
            state=state,
            slope=slope,
            confidence=self._compute_confidence(landmarks),
            landmarks=results.pose_landmarks,
        )

    def shutdown(self) -> None:
        """Release both pose models in addition to base camera shutdown."""

        super().shutdown()
        if self._pose_models:
            for model in self._pose_models:
                if model is not None:
                    model.close()
            self._pose_models = None
