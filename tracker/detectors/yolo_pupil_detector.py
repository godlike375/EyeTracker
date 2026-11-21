import cv2
import numpy

from tracker.detectors.detectors import PupilDetector
from tracker.utils.shared_objects import INITIAL_VALUE, SharedBox


DEFAULT_CONF = 0.25
DEFAULT_IMGSZ = 192


class YoloPupilDetector(PupilDetector):
    """Pupil detector based on a YOLO segmentation model.

    Runs the model on the eye region (``detect_area``) and reports the center
    of the segmentation mask of the most relevant detection.

    Center estimation (``use_ellipse``):
      * True  -> center of an ellipse fitted to the mask contour (more robust
                 to asymmetric masks / partial occlusion than the centroid);
      * False -> centroid of the mask (``cv2.moments``).
    Falls back to the box center when no usable mask is available.

    Detection selection (``associate``):
      * True  -> among all detections pick the one closest to the center found
                 on the previous frame (temporal association);
      * False -> pick the largest mask (legacy behavior).
    """

    def __init__(self, model_path, conf: float = DEFAULT_CONF, imgsz: int = DEFAULT_IMGSZ,
                 use_ellipse: bool = True, associate: bool = True, *args, **kwargs):
        self.model_path = model_path
        self.conf = float(conf)
        self.imgsz = int(imgsz)
        self.use_ellipse = use_ellipse
        self.associate = associate
        self.model = None
        self.last_box = SharedBox('i', INITIAL_VALUE)
        self.last_conf = 0.0
        self._last_center = None
        super().__init__(*args, **kwargs)

    def in_process_init(self):
        from ultralytics import YOLO
        self._adopt_exported_imgsz()
        try:
            self.model = YOLO(self.model_path, task='detect')
        except Exception:
            self.model = YOLO(self.model_path)
        self._last_center = None
        super().in_process_init()

    def _adopt_exported_imgsz(self):
        """Exported models (e.g. OpenVINO) have a fixed input shape; adopt it
        so a mismatched ``imgsz`` setting can't crash inference."""
        import os
        if not os.path.isdir(self.model_path):
            return
        meta_path = os.path.join(self.model_path, 'metadata.yaml')
        if not os.path.isfile(meta_path):
            return
        try:
            import yaml
            with open(meta_path, encoding='utf-8') as stream:
                meta = yaml.safe_load(stream) or {}
            imgsz = meta.get('imgsz')
            if isinstance(imgsz, (list, tuple)) and imgsz:
                self.imgsz = int(imgsz[0])
            elif isinstance(imgsz, int):
                self.imgsz = int(imgsz)
        except Exception:
            pass

    def detect(self, raw: numpy.ndarray):
        try:
            eye = self.get_eye_rgb_frame(raw)
        except Exception:
            self._invalidate()
            return
        if eye is None or eye.size == 0:
            self._invalidate()
            return

        results = self.model(eye, verbose=False, imgsz=self.imgsz, conf=self.conf)
        candidates = list(self._iter_candidates(results[0], eye.shape[1], eye.shape[0]))
        candidates = self._filter_iris_candidates(candidates)
        best = self._select(candidates)

        if best is None:
            self._invalidate()
            return

        cx, cy, box, conf = best[:4]
        ox, oy = self.detect_area.x1, self.detect_area.y1
        self.pupil.array[:] = int(cx + ox), int(cy + oy)
        self.last_box.x1 = int(box[0]) + ox
        self.last_box.y1 = int(box[1]) + oy
        self.last_box.x2 = int(box[2]) + ox
        self.last_box.y2 = int(box[3]) + oy
        self.last_conf = conf
        self._last_center = (cx, cy)

    def _invalidate(self):
        self.pupil.invalidate()
        self.last_box.invalidate()
        self._last_center = None

    def _iter_candidates(self, result, width: int, height: int):
        boxes = getattr(result, 'boxes', None)
        if boxes is None or len(boxes) == 0:
            return
        masks = getattr(result, 'masks', None)
        for i in range(len(boxes)):
            box = boxes.xyxy[i].cpu().numpy()
            conf = float(boxes.conf[i])
            center = None
            area = 0.0
            if masks is not None and masks.data is not None and i < len(masks.data):
                mask = masks.data[i].cpu().numpy().astype(numpy.float32)
                mask = cv2.resize(mask, (width, height), interpolation=cv2.INTER_NEAREST)
                binary = (mask > 0.5).astype(numpy.uint8)
                area = float(binary.sum())
                if area > 0:
                    center = self._mask_center(binary, box)
            if center is None:
                center = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
            yield (center[0], center[1], box, conf, area)

    def _mask_center(self, binary: numpy.ndarray, box):
        if self.use_ellipse:
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            if contours:
                contour = max(contours, key=cv2.contourArea)
                if len(contour) >= 5:
                    (ex, ey), _, _ = cv2.fitEllipse(contour)
                    return float(ex), float(ey)

        moments = cv2.moments(binary, binaryImage=True)
        if moments['m00'] > 0:
            return moments['m10'] / moments['m00'], moments['m01'] / moments['m00']
        return (box[0] + box[2]) / 2, (box[1] + box[3]) / 2

    def _select(self, candidates):
        if not candidates:
            return None
        if self.associate and self._last_center is not None:
            lx, ly = self._last_center
            return min(candidates, key=lambda c: (c[0] - lx) ** 2 + (c[1] - ly) ** 2)
        # For detection models without masks (area == 0), select candidate with highest confidence (c[3])
        return max(candidates, key=lambda c: (c[4], c[3]))

    def _filter_iris_candidates(self, candidates):
        """If one detection is nested inside (or largely overlaps and is enclosed by)
        another significantly larger detection, the smaller one is the anatomical pupil
        and the larger one is the iris/orbit. Suppress the larger enclosing candidate."""
        if len(candidates) < 2:
            return candidates

        suppressed = set()
        n = len(candidates)
        for i in range(n):
            if i in suppressed:
                continue
            cx_i, cy_i, box_i, conf_i, _ = candidates[i]
            area_i = max(1.0, float((box_i[2] - box_i[0]) * (box_i[3] - box_i[1])))

            for j in range(n):
                if i == j or j in suppressed:
                    continue
                cx_j, cy_j, box_j, conf_j, _ = candidates[j]
                area_j = max(1.0, float((box_j[2] - box_j[0]) * (box_j[3] - box_j[1])))

                # Check if box_i is significantly smaller than box_j (at least 1.35x smaller)
                if area_j >= 1.35 * area_i:
                    ix1 = max(box_i[0], box_j[0])
                    iy1 = max(box_i[1], box_j[1])
                    ix2 = min(box_i[2], box_j[2])
                    iy2 = min(box_i[3], box_j[3])
                    inter_w = max(0.0, ix2 - ix1)
                    inter_h = max(0.0, iy2 - iy1)
                    inter_area = inter_w * inter_h

                    containment = inter_area / area_i
                    center_inside = (box_j[0] <= cx_i <= box_j[2]) and (box_j[1] <= cy_i <= box_j[3])

                    if containment >= 0.60 or center_inside:
                        # box_j encloses box_i -> box_j is an iris/orbit candidate, suppress it!
                        suppressed.add(j)

        return [c for idx, c in enumerate(candidates) if idx not in suppressed]
