from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

import cv2
import mediapipe as mp

@dataclass
class PoseControl:
    x: float
    y: float
    confidence: float

class PoseState(str, Enum):
    NO_POSE = "no_pose"
    T_POSE = "t_pose"
    HANDS_UP = "hands_up"
    HANDS_DOWN = "hands_down"

class PoseController:
    """Wraps MediaPipe Pose to provide normalized control coordinates."""

    def __init__(self, camera_index: int = 0, mirror: bool = True) -> None:
        self.camera_index = camera_index
        self.mirror = mirror
        self.available = bool(cv2 and mp)
        self._pose = None
        self._cap = None
        self._last_control = PoseControl(0.5, 0.7, 0.0)
        self._last_state = PoseState.NO_POSE
        self._last_slope = 0.0
        self._last_frame: Optional[Any] = None  # Raw BGR frame from OpenCV
        self._last_landmarks = None
        if self.available:
            self._boot_hardware()

    def _boot_hardware(self) -> None:
        assert cv2 is not None and mp is not None
        self._cap = cv2.VideoCapture(self.camera_index)
        if not self._cap.isOpened():
            self.available = False
            return
        mp_pose = mp.solutions.pose
        self._pose = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)

    def read(self) -> Optional[PoseControl]:
        if not self.available or self._cap is None or self._pose is None:
            return None

        ok, frame = self._cap.read()
        if not ok:
            self._last_state = PoseState.NO_POSE
            self._last_slope = 0.0
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
            self._last_landmarks = None
            return None

        landmarks = results.pose_landmarks.landmark
        mp_pose = mp.solutions.pose
        primary = landmarks[mp_pose.PoseLandmark.NOSE]
        left_shoulder = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER]
        right_shoulder = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER]
        left_hip = landmarks[mp_pose.PoseLandmark.LEFT_HIP]
        right_hip = landmarks[mp_pose.PoseLandmark.RIGHT_HIP]

        avg_shoulder_x = (left_shoulder.x + right_shoulder.x) / 2
        avg_hip_y = (left_hip.y + right_hip.y) / 2

        confidence = max(0.0, min(1.0, (primary.visibility + left_shoulder.visibility + right_shoulder.visibility) / 3))
        control = PoseControl(x=avg_shoulder_x, y=avg_hip_y, confidence=confidence)
        self._last_control = control
        self._last_landmarks = results.pose_landmarks
        self._last_state = self._classify_state(landmarks)
        return control

    def _classify_state(self, landmarks) -> PoseState:
        assert mp is not None
        mp_pose = mp.solutions.pose
        left_shoulder = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER]
        right_shoulder = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER]
        left_wrist = landmarks[mp_pose.PoseLandmark.LEFT_WRIST]
        right_wrist = landmarks[mp_pose.PoseLandmark.RIGHT_WRIST]

        left_wrist_vis = getattr(left_wrist, "visibility", 1.0)
        right_wrist_vis = getattr(right_wrist, "visibility", 1.0)
        min_wrist_visibility = min(left_wrist_vis, right_wrist_vis)
        visibility_threshold = 0.45
        if min_wrist_visibility < visibility_threshold:
            self._last_slope = 0.0
            return PoseState.NO_POSE

        dx = right_wrist.x - left_wrist.x
        if abs(dx) < 1e-5:
            dx = 1e-5 if dx >= 0 else -1e-5
        slope = (right_wrist.y - left_wrist.y) / dx
        self._last_slope = slope

        avg_shoulder_y = (left_shoulder.y + right_shoulder.y) / 2
        up_margin = 0.05
        down_margin = 0.05

        if left_wrist.y < avg_shoulder_y - up_margin and right_wrist.y < avg_shoulder_y - up_margin:
            return PoseState.HANDS_UP

        if left_wrist.y > avg_shoulder_y + down_margin and right_wrist.y > avg_shoulder_y + down_margin:
            return PoseState.HANDS_DOWN

        shoulder_span = max(abs(right_shoulder.x - left_shoulder.x), 1e-5)
        wrist_span = abs(right_wrist.x - left_wrist.x)
        arms_extended = wrist_span >= shoulder_span * 0.6

        alignment_tolerance = 0.1
        left_inline = abs(left_wrist.y - left_shoulder.y) <= alignment_tolerance
        right_inline = abs(right_wrist.y - right_shoulder.y) <= alignment_tolerance
        if left_inline and right_inline or arms_extended:
            return PoseState.T_POSE

        return PoseState.NO_POSE

    @property
    def state(self) -> PoseState:
        return self._last_state or PoseState.NO_POSE

    @property
    def control(self) -> PoseControl:
        return self._last_control

    @property
    def frame(self):
        return self._last_frame

    @property
    def landmarks(self):
        return self._last_landmarks
    
    @property
    def turn_slope(self) -> float:
        return self._last_slope

    def shutdown(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        if self._pose is not None:
            self._pose.close()
            self._pose = None

    def __del__(self) -> None:
        self.shutdown()
