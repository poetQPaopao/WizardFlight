from __future__ import annotations

import argparse
import sys
import time
import cv2
import mediapipe as mp
from .pose_input import (
    DualPoseController,
    PoseController,
    PoseReading,
    PoseState,
)

MP_DRAWING = mp.solutions.drawing_utils
MP_STYLES = mp.solutions.drawing_styles
MP_POSE = mp.solutions.pose

STATE_LABELS = {
    PoseState.T_POSE: "T-Pose",
    PoseState.HANDS_UP: "Hands Up",
    PoseState.HANDS_DOWN: "Hands Down",
    PoseState.NO_POSE: "No Pose",
}

WINDOW_NAME = "Pose Input Test"

def format_states(active_state: PoseState) -> str:
    parts = []
    for state in PoseState:
        marker = ">" if state == active_state else " "
        parts.append(f"{marker} {STATE_LABELS[state]}")
    return " | ".join(parts)


def draw_overlay(frame, landmarks, state: PoseState, confidence: float, slope: float):
    if frame is None:
        return None
    output = frame.copy()
    wrist_points = None
    if landmarks is not None:
        MP_DRAWING.draw_landmarks(
            output,
            landmarks,
            MP_POSE.POSE_CONNECTIONS,
            landmark_drawing_spec=None if MP_STYLES is None else MP_STYLES.get_default_pose_landmarks_style(),
        )
        lm = landmarks.landmark
        left = lm[MP_POSE.PoseLandmark.LEFT_WRIST]
        right = lm[MP_POSE.PoseLandmark.RIGHT_WRIST]
        h, w = output.shape[:2]
        wrist_points = (
            (int(left.x * w), int(left.y * h)),
            (int(right.x * w), int(right.y * h)),
        )
        cv2.line(output, wrist_points[0], wrist_points[1], (0, 255, 255), 3)
    label = STATE_LABELS.get(state, STATE_LABELS[PoseState.NO_POSE])
    status = f"{label} | conf={confidence:.2f} slope={slope:+.2f}"
    cv2.rectangle(output, (6, 6), (440, 60), (15, 15, 15), thickness=cv2.FILLED)
    cv2.putText(output, status, (12, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (240, 240, 240), 2)
    cv2.putText(
        output,
        "Press ESC or Q to quit",
        (12, output.shape[0] - 16),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (255, 255, 255),
        1,
    )
    return output


def draw_dual_overlay(frame, readings: tuple[PoseReading | None, PoseReading | None]):
    if frame is None:
        return None
    output = frame.copy()
    height, width = output.shape[:2]
    mid = width // 2
    regions = (
        (0, mid),
        (mid, width - mid),
    )
    title_colors = ((120, 245, 200), (120, 190, 255))
    for idx, (x0, region_width) in enumerate(regions):
        if region_width <= 0:
            continue
        region_view = output[:, x0 : x0 + region_width]
        reading = readings[idx] if idx < len(readings) else None
        state = reading.state if reading else PoseState.NO_POSE
        label = STATE_LABELS.get(state, STATE_LABELS[PoseState.NO_POSE])
        confidence = reading.confidence if reading else 0.0
        slope = reading.slope if reading else 0.0

        if reading and reading.landmarks is not None and MP_DRAWING and MP_POSE:
            MP_DRAWING.draw_landmarks(
                region_view,
                reading.landmarks,
                MP_POSE.POSE_CONNECTIONS,
                landmark_drawing_spec=None
                if MP_STYLES is None
                else MP_STYLES.get_default_pose_landmarks_style(),
            )
            lm = reading.landmarks.landmark
            left = lm[MP_POSE.PoseLandmark.LEFT_WRIST]
            right = lm[MP_POSE.PoseLandmark.RIGHT_WRIST]
            region_h, region_w = region_view.shape[:2]
            wrist_line = (
                (int(left.x * region_w), int(left.y * region_h)),
                (int(right.x * region_w), int(right.y * region_h)),
            )
            cv2.line(region_view, wrist_line[0], wrist_line[1], (0, 255, 255), 3)

        panel_tl = (x0 + 8, 8)
        panel_br = (x0 + region_width - 8, 72)
        cv2.rectangle(output, panel_tl, panel_br, (15, 15, 15), thickness=cv2.FILLED)
        header = f"P{idx + 1}: {label}"
        cv2.putText(
            output,
            header,
            (panel_tl[0] + 6, panel_tl[1] + 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            title_colors[idx],
            2,
        )
        metrics = f"conf={confidence:.2f} slope={slope:+.2f}"
        cv2.putText(
            output,
            metrics,
            (panel_tl[0] + 6, panel_tl[1] + 48),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (230, 230, 230),
            1,
        )

    cv2.line(output, (mid, 0), (mid, height), (80, 80, 80), 1)
    cv2.putText(
        output,
        "Dual mode – Press ESC or Q to quit",
        (12, height - 16),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (255, 255, 255),
        1,
    )
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pose overlay visualizer.")
    parser.add_argument(
        "--dual",
        action="store_true",
        help="Split the camera feed and visualize two poses side-by-side",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ControllerCls = DualPoseController if args.dual else PoseController
    controller = ControllerCls()
    try:
        if isinstance(controller, DualPoseController):
            while True:
                readings = controller.read_pair()
                frame = controller.frame
                overlay = draw_dual_overlay(frame, readings)
                if overlay is not None:
                    cv2.imshow(WINDOW_NAME, overlay)
                    key = cv2.waitKey(1) & 0xFF
                    if key in (27, ord("q"), ord("Q")):
                        break
                time.sleep(0.01)
        else:
            while True:
                state = controller.read() or controller.state or PoseState.NO_POSE
                slope = controller.turn_slope
                confidence = controller.confidence

                frame = controller.frame
                overlay = draw_overlay(
                    frame,
                    controller.landmarks,
                    state,
                    confidence,
                    slope,
                )
                if overlay is not None:
                    cv2.imshow(WINDOW_NAME, overlay)
                    key = cv2.waitKey(1) & 0xFF
                    if key in (27, ord("q"), ord("Q")):
                        break

                time.sleep(0.01)
    except KeyboardInterrupt:
        print("\nStopping pose input test.")
    finally:
        controller.shutdown()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
