import cv2
import numpy as np
from ultralytics import YOLO
from config import MODEL_PATH
from services.severity import calculate_severity

_model = None

def get_model() -> YOLO:
    global _model
    if _model is None:
        _model = YOLO(MODEL_PATH)
    return _model

def run_inference(image_bytes: bytes) -> dict:
    model = get_model()

    nparr = np.frombuffer(image_bytes, np.uint8)
    img   = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    h, w  = img.shape[:2]
    image_area = h * w

    results = model(img, verbose=False)[0]

    detections = []
    for box in results.boxes:
        cls_id       = int(box.cls[0])
        disease_name = model.names[cls_id]
        confidence   = round(float(box.conf[0]) * 100, 1)
        x1, y1, x2, y2 = [round(float(v), 2) for v in box.xyxy[0]]
        box_area     = (x2 - x1) * (y2 - y1)
        severity     = calculate_severity(box_area, image_area)

        detections.append({
            "disease":    disease_name,
            "confidence": confidence,
            "severity":   severity,
            "bbox":       {"x1": x1, "y1": y1, "x2": x2, "y2": y2}
        })

    if not detections:
        return {"status": "healthy", "detections": []}

    detections.sort(key=lambda d: d["confidence"], reverse=True)
    return {"status": "diseased", "detections": detections}