from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, TYPE_CHECKING

import pygame

if TYPE_CHECKING:  # pragma: no cover - typing time only
    from controller.pose_detection.pose_input import PoseReading

POSE_CONFIDENCE_THRESHOLD = 0.45
POSE_SLOPE_DEADZONE = 0.2


@dataclass(frozen=True, slots=True)
class ControlScheme:
    """Keyboard mapping for a player."""

    up: int
    down: int
    left: int
    right: int
    cast: int

    @classmethod
    def wasd(cls) -> ControlScheme:
        """Default controls for Player 1."""
        return cls(
            up=pygame.K_w,
            down=pygame.K_s,
            left=pygame.K_a,
            right=pygame.K_d,
            cast=pygame.K_SPACE,
        )

    @classmethod
    def arrow_keys(cls) -> ControlScheme:
        """Default controls for Player 2."""
        return cls(
            up=pygame.K_UP,
            down=pygame.K_DOWN,
            left=pygame.K_LEFT,
            right=pygame.K_RIGHT,
            cast=pygame.K_RSHIFT,
        )


class PoseKeyState(Sequence[bool]):
    """Sequence wrapper that overrides select keys with pose-driven values."""

    def __init__(self, overrides: dict[int, bool], fallback: Sequence[bool]) -> None:
        self._overrides = overrides
        self._fallback = fallback

    def __getitem__(self, key: int) -> bool:
        if key in self._overrides:
            return self._overrides[key]
        return self._fallback[key]

    def __len__(self) -> int:
        return len(self._fallback)


class PoseControlSystem:
    """Owns the pose-controller lifecycle and converts readings to key overrides."""

    def __init__(self, max_players: int, overlay_window: str = "Pose Input") -> None:
        self.max_players = max_players
        self.overlay_window = overlay_window
        self.controller = self._build_pose_controller()
        self._readings: list[Optional["PoseReading"]] = [None] * max_players
        self._quit_requested = False

    def tick(self) -> None:
        """Refresh pose readings and note if the overlay window requested exit."""
        self._quit_requested = False
        if not self.controller:
            self._set_idle_state()
            return
        try:
            raw_readings = self.controller.read_pair()
        except Exception as exc:  # pragma: no cover - hardware specific
            print(f"[pose] Controller error: {exc}")
            self.controller.shutdown()
            self.controller = None
            self._set_idle_state()
            return
        self._sync_readings(raw_readings)
        self._show_overlay(raw_readings)

    def build_overrides(self, index: int, scheme: ControlScheme) -> dict[int, bool]:
        """Return pygame key overrides for the given player slot."""
        reading: Optional["PoseReading"] = None
        if 0 <= index < len(self._readings):
            reading = self._readings[index]
        return pose_reading_to_overrides(reading, scheme)

    @property
    def quit_requested(self) -> bool:
        return self._quit_requested

    @property
    def active(self) -> bool:
        return self.controller is not None

    def shutdown(self) -> None:
        """Tear down the controller and close any overlay windows."""
        if self.controller:
            self.controller.shutdown()
            self.controller = None
        try:
            import cv2

            cv2.destroyWindow(self.overlay_window)
        except Exception:  # pragma: no cover - best effort cleanup
            pass

    def _sync_readings(self, raw_readings: Sequence[Optional["PoseReading"]]) -> None:
        self._readings = [
            raw_readings[idx] if idx < len(raw_readings) else None for idx in range(self.max_players)
        ]

    def _set_idle_state(self) -> None:
        self._readings = [None] * self.max_players

    def _show_overlay(self, raw_readings: Sequence[Optional["PoseReading"]]) -> None:
        if not self.controller:
            return
        try:
            from controller.pose_detection.pose_input_test import draw_dual_overlay
            import cv2
        except ImportError:
            return

        overlay = draw_dual_overlay(self.controller.frame, raw_readings)
        if overlay is not None:
            cv2.imshow(self.overlay_window, overlay)
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q"), ord("Q")):
                self._quit_requested = True

    @staticmethod
    def _build_pose_controller():
        try:
            from controller.pose_detection.pose_input import DualPoseController
        except ImportError:
            return None

        controller = DualPoseController()
        if not controller.available:
            controller.shutdown()
            return None
        return controller


def pose_reading_to_overrides(
    reading: Optional["PoseReading"], scheme: ControlScheme
) -> dict[int, bool]:
    """Translate a pose reading to pygame key states aligned with the scheme."""
    if reading is None or reading.confidence < POSE_CONFIDENCE_THRESHOLD:
        return {}
    try:
        from controller.pose_detection.pose_input import PoseState
    except ImportError:
        return {}

    overrides: dict[int, bool] = {}
    slope = reading.slope
    if slope < -POSE_SLOPE_DEADZONE:
        overrides[scheme.left] = True
    if slope > POSE_SLOPE_DEADZONE:
        overrides[scheme.right] = True

    if PoseState is not None:
        if reading.state == PoseState.HANDS_UP:
            overrides[scheme.up] = True
        elif reading.state == PoseState.HANDS_DOWN:
            overrides[scheme.down] = True

    return overrides
