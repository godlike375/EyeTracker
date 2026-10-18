import cv2
import numpy

from tracker.detectors.detectors import PupilDetector
from tracker.utils.shared_objects import INITIAL_VALUE, SharedBox


DEFAULT_CONF = 0.25
DEFAULT_IMGSZ = 192


class YoloPupilDetector(PupilDetector):
    """Pupil detector based on a YOLO segmentation model.

    Runs the model on the eye region (``detect_area``) and reports the
    centroid of the segmentation mask of the most relevant detection.
    """

    def __init__(self, model_path, conf: float = DEFAULT_CONF, imgsz: int = DEFAULT_IMGSZ,
                 use_centroid: bool = True, *args, **kwargs):
        self.model_path = model_path
        self.conf = float(conf)
        self.imgsz = int(imgsz)
        self.use_centroid = use_centroid
        self.model = None
        self.last_box = SharedBox('i', INITIAL_VALUE)
        self.last_conf = 0.0
        super().__init__(*args, **kwargs)

    def in_process_init(self):
        from ultralytics import YOLO
        self.model = YOLO(self.model_path)
        super().in_process_init()

    def detect(self, raw: numpy.ndarray):
        try:
            eye = self.get_eye_rgb_frame(raw)
        except Exception:
            self.pupil.invalidate()
            self.last_box.invalidate()
            return
        if eye is None or eye.size == 0:
            self.pupil.invalidate()
            self.last_box.invalidate()
            return

        results = self.model(eye, verbose=False, imgsz=self.imgsz, conf=self.conf)
        result = results[0]
        best = self._pick_best(result, eye.shape[1], eye.shape[0])

        if best is None:
            self.pupil.invalidate()
            self.last_box.invalidate()
            return

        area, cx, cy, box, conf = best
        ox, oy = self.detect_area.x1, self.detect_area.y1
        self.pupil.array[:] = int(cx + ox), int(cy + oy)
        self.last_box.x1 = int(box[0]) + ox
        self.last_box.y1 = int(box[1]) + oy
        self.last_box.x2 = int(box[2]) + ox
        self.last_box.y2 = int(box[3]) + oy
        self.last_conf = conf

    def _pick_best(self, result, width: int, height: int):
        boxes = getattr(result, 'boxes', None)
        if boxes is None or len(boxes) == 0:
            return None
        masks = getattr(result, 'masks', None)
        best = None
        for i in range(len(boxes)):
            box = boxes.xyxy[i].cpu().numpy()
            conf = float(boxes.conf[i])
            if masks is not None and masks.data is not None and i < len(masks.data):
                mask = masks.data[i].cpu().numpy().astype(numpy.float32)
                mask = cv2.resize(mask, (width, height), interpolation=cv2.INTER_NEAREST)
                binary = (mask > 0.5).astype(numpy.uint8)
                area = float(binary.sum())
                if area > 0:
                    moments = cv2.moments(binary, binaryImage=True)
                    cx = moments['m10'] / moments['m00']
                    cy = moments['m01'] / moments['m00']
                else:
                    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
                    area = 0.0
            else:
                cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
                area = (box[2] - box[0]) * (box[3] - box[1])
            if best is None or area > best[0]:
                best = (area, cx, cy, box, conf)
        return best
