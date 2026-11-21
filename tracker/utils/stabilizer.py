import cv2
import numpy as np


class OpticalFlowStabilizer:
    """Real-time Electronic Image Stabilization (EIS) using sparse optical flow (Lucas-Kanade)
    and RANSAC rigid transform estimation, with trajectory smoothing and border margin crop.
    """

    def __init__(self, crop_ratio: float = 0.85, smoothing_window: int = 15, target_flow_h: int = 360):
        self.crop_ratio = float(crop_ratio)
        self.smoothing_window = max(3, int(smoothing_window))
        self.target_flow_h = int(target_flow_h)
        self.reset()

    def reset(self):
        self.prev_gray = None
        self.prev_points = None
        self.cum_x = 0.0
        self.cum_y = 0.0
        self.cum_a = 0.0
        self.history_x = []
        self.history_y = []
        self.history_a = []
        self.frame_count = 0

    def process(self, frame: np.ndarray) -> np.ndarray:
        if frame is None or frame.size == 0:
            return frame

        h, w = frame.shape[:2]
        scale = min(1.0, self.target_flow_h / float(max(1, h)))
        small_w, small_h = int(round(w * scale)), int(round(h * scale))
        small_gray = cv2.cvtColor(cv2.resize(frame, (small_w, small_h)), cv2.COLOR_BGR2GRAY)

        # Re-detect corner features periodically or if point count is low
        if (self.prev_gray is None or self.prev_points is None or
                len(self.prev_points) < 30 or self.frame_count % 30 == 0):
            self.prev_points = cv2.goodFeaturesToTrack(
                small_gray, maxCorners=120, qualityLevel=0.02, minDistance=15
            )
            self.prev_gray = small_gray
            if self.prev_points is None or len(self.prev_points) < 10:
                return self._apply_identity_crop(frame, w, h)

        # Lucas-Kanade optical flow on pyramid
        p1, status, _ = cv2.calcOpticalFlowPyrLK(
            self.prev_gray, small_gray, self.prev_points, None,
            winSize=(21, 21), maxLevel=3
        )

        if status is None:
            self.reset()
            return self._apply_identity_crop(frame, w, h)

        valid_idx = (status.flatten() == 1)
        good_prev = self.prev_points[valid_idx]
        good_curr = p1[valid_idx]

        if len(good_curr) < 10:
            self.reset()
            return self._apply_identity_crop(frame, w, h)

        # Rigid 2D Euclidean motion with RANSAC outlier rejection
        matrix, inliers = cv2.estimateAffinePartial2D(
            good_prev, good_curr, method=cv2.RANSAC, ransacReprojThreshold=3.0
        )

        if matrix is None:
            self.reset()
            return self._apply_identity_crop(frame, w, h)

        self.prev_gray = small_gray
        self.prev_points = good_curr.reshape(-1, 1, 2)
        self.frame_count += 1

        # Rescale translation to full-frame coordinates
        dx = matrix[0, 2] / scale
        dy = matrix[1, 2] / scale
        da = np.arctan2(matrix[1, 0], matrix[0, 0])

        # Accumulate trajectory
        self.cum_x += dx
        self.cum_y += dy
        self.cum_a += da

        self.history_x.append(self.cum_x)
        self.history_y.append(self.cum_y)
        self.history_a.append(self.cum_a)

        if len(self.history_x) > self.smoothing_window:
            self.history_x.pop(0)
            self.history_y.pop(0)
            self.history_a.pop(0)

        smooth_x = sum(self.history_x) / len(self.history_x)
        smooth_y = sum(self.history_y) / len(self.history_y)
        smooth_a = sum(self.history_a) / len(self.history_a)

        # High-frequency shake compensation offset
        diff_x = smooth_x - self.cum_x
        diff_y = smooth_y - self.cum_y
        diff_a = smooth_a - self.cum_a

        # Clamp offsets to crop margin buffer to prevent borders
        max_dx = w * (1.0 - self.crop_ratio) / 2.0
        max_dy = h * (1.0 - self.crop_ratio) / 2.0
        max_da = 0.087  # ~5 deg max rotation

        diff_x = np.clip(diff_x, -max_dx, max_dx)
        diff_y = np.clip(diff_y, -max_dy, max_dy)
        diff_a = np.clip(diff_a, -max_da, max_da)

        # Push cumulative trajectory when clamped (smooth camera following)
        self.cum_x = smooth_x - diff_x
        self.cum_y = smooth_y - diff_y
        self.cum_a = smooth_a - diff_a

        # Construct warp matrix: translate + rotate + zoom by 1/crop_ratio
        cx, cy = w / 2.0, h / 2.0
        scale_zoom = 1.0 / self.crop_ratio
        cos_a = np.cos(diff_a) * scale_zoom
        sin_a = np.sin(diff_a) * scale_zoom

        tx = cx - cos_a * cx + sin_a * cy + diff_x * scale_zoom
        ty = cy - sin_a * cx - cos_a * cy + diff_y * scale_zoom

        M = np.array([
            [cos_a, -sin_a, tx],
            [sin_a,  cos_a, ty]
        ], dtype=np.float32)

        return cv2.warpAffine(frame, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

    def _apply_identity_crop(self, frame: np.ndarray, w: int, h: int) -> np.ndarray:
        scale_zoom = 1.0 / self.crop_ratio
        cx, cy = w / 2.0, h / 2.0
        tx = cx * (1.0 - scale_zoom)
        ty = cy * (1.0 - scale_zoom)
        M = np.array([
            [scale_zoom, 0.0, tx],
            [0.0, scale_zoom, ty]
        ], dtype=np.float32)
        return cv2.warpAffine(frame, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
