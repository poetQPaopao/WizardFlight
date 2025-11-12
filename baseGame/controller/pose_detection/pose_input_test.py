from __future__ import annotations

import sys
import time
import cv2
import mediapipe as mp
from controller.pose_detection.pose_input import PoseController, PoseState

STATE_LABELS = {
    PoseState.T_POSE: "T-Pose",
    PoseState.HANDS_UP: "Hands Up",
    PoseState.HANDS_DOWN: "Hands Down",
    PoseState.NO_POSE: "No Pose",
}

WINDOW_NAME = "Pose Input Test"
MP_DRAWING = mp.solutions.drawing_utils
MP_STYLES = mp.solutions.drawing_styles
MP_POSE = mp.solutions.pose

def format_states(active_state: PoseState) -> str:
    parts = []
    for state in PoseState:
        marker = ">" if state == active_state else " "
        parts.append(f"{marker} {STATE_LABELS[state]}")
    return " | ".join(parts)


def draw_overlay(frame, landmarks, state: PoseState, control_x: float, control_y: float, confidence: float, slope: float):
    if frame is None:
        return None
    output = frame.copy()
    wrist_points = None
    if landmarks is not None and MP_DRAWING and MP_POSE:
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
    status = f"{label} | x={control_x:.2f} y={control_y:.2f} conf={confidence:.2f} slope={slope:+.2f}"
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


def main() -> None:
    controller = PoseController()
    if not controller.available:
        print(
            "PoseController unavailable. Ensure a webcam is connected and install mediapipe + opencv-python.",
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        while True:
            control = controller.read()
            # Use last stable control when detection drops momentarily.
            control = control or controller.control
            state = controller.state or PoseState.NO_POSE
            slope = controller.turn_slope

            frame = controller.frame
            overlay = draw_overlay(
                frame,
                controller.landmarks,
                state,
                control.x,
                control.y,
                control.confidence,
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
