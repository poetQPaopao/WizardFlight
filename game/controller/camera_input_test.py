import cv2
import mediapipe as mp
from collections import deque

# 手势到方向的映射：
# - 右手抬起 => right
# - 左手抬起 => left
# - 扇动双臂 => forward
# - 手臂自然下垂且基本不动 => back
# - 其他/不确定 => none

LEFT_LABEL = "left"
RIGHT_LABEL = "right"
FORWARD_LABEL = "forward"
BACK_LABEL = "back"
NONE_LABEL = "none"


class PoseGestureClassifier:
    def __init__(self,
                 raise_margin: float = 0.04,     # 手腕高于同侧肩的最小高度差（y 更小更高）
                 flat_y_tol: float = 0.05,       # （保留参数：若需要“平举”检测可用）
                 flat_x_ratio: float = 0.25,     # （保留参数）
                 flap_window: int = 24,          # 扇动检测窗口帧数
                 flap_amp_thresh: float = 0.06,  # 扇动振幅阈值（y 的峰-谷）
                 still_amp_thresh: float = 0.015, # 静止阈值（y 振幅很小）
                 down_margin: float = 0.04       # 手腕低于同侧髋部的最小高度差（y 更大更低）
                 ):
        self.raise_margin = raise_margin
        self.flat_y_tol = flat_y_tol
        self.flat_x_ratio = flat_x_ratio
        self.flap_window = flap_window
        self.flap_amp_thresh = flap_amp_thresh
        self.still_amp_thresh = still_amp_thresh
        self.down_margin = down_margin

        mp_pose = mp.solutions.pose
        self.pose = mp_pose.Pose()
        self.mp_pose = mp_pose
        self.mp_draw = mp.solutions.drawing_utils

        self.wrist_hist_left = deque(maxlen=flap_window)
        self.wrist_hist_right = deque(maxlen=flap_window)
        self._last_direction = NONE_LABEL

    def _amp(self, hist: deque[float]) -> float:
        if not hist:
            return 0.0
        return max(hist) - min(hist)

    def update_and_classify(self, frame_bgr):
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        result = self.pose.process(rgb)

        direction = NONE_LABEL
        if result.pose_landmarks:
            lm = result.pose_landmarks.landmark
            P = self.mp_pose.PoseLandmark

            def L(k):
                return lm[k.value]

            l_sh, r_sh = L(P.LEFT_SHOULDER), L(P.RIGHT_SHOULDER)
            l_hp, r_hp = L(P.LEFT_HIP), L(P.RIGHT_HIP)
            l_wr, r_wr = L(P.LEFT_WRIST), L(P.RIGHT_WRIST)

            # 更新历史（y 越小越高）
            self.wrist_hist_left.append(l_wr.y)
            self.wrist_hist_right.append(r_wr.y)

            shoulder_width = abs(l_sh.x - r_sh.x)
            min_dx = self.flat_x_ratio * max(shoulder_width, 1e-3)

            # 1) 抬手：右/左（优先）
            right_raised = (r_wr.y < (r_sh.y - self.raise_margin))
            left_raised = (l_wr.y < (l_sh.y - self.raise_margin))
            if right_raised and not left_raised:
                direction = RIGHT_LABEL
            elif left_raised and not right_raised:
                direction = LEFT_LABEL
            else:
                # 2) 扇动双臂 => forward（检测最近窗口振幅是否足够大，至少一侧明显扇动，通常两侧都大更稳健）
                amp_left = self._amp(self.wrist_hist_left)
                amp_right = self._amp(self.wrist_hist_right)
                flapping = (amp_left > self.flap_amp_thresh and amp_right > self.flap_amp_thresh)

                if flapping:
                    direction = FORWARD_LABEL
                else:
                    # 3) 手臂自然下垂且基本不动 => back
                    # 判定：两侧手腕 y 明显低于同侧髋部 y（下垂），且最近窗口振幅很小（不怎么动）
                    left_down = (l_wr.y >= (l_hp.y + self.down_margin))
                    right_down = (r_wr.y >= (r_hp.y + self.down_margin))
                    amp_small = (amp_left < self.still_amp_thresh and amp_right < self.still_amp_thresh)
                    if left_down and right_down and amp_small:
                        direction = BACK_LABEL
                    else:
                        direction = NONE_LABEL

        changed = (direction != self._last_direction)
        self._last_direction = direction
        return direction, changed, result


def main():
    cap = cv2.VideoCapture(0)
    classifier = PoseGestureClassifier()

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        direction, changed, result = classifier.update_and_classify(frame)

        # 叠加可视化
        if result and result.pose_landmarks:
            classifier.mp_draw.draw_landmarks(frame, result.pose_landmarks, classifier.mp_pose.POSE_CONNECTIONS)
        cv2.putText(frame, f"dir: {direction}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1,
                    (0, 255, 0) if direction != NONE_LABEL else (0, 200, 200), 2)

        # 控制台仅在变化时输出
        if changed and direction != NONE_LABEL:
            print("direction:", direction)

        cv2.imshow("Pose Tracking", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == 27:  # ESC 退出
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()