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

SEVERITY_COLORS = {
    "Mild":     (0, 255, 0),    # green
    "Moderate": (0, 165, 255),  # orange
    "Severe":   (0, 0, 255),    # red
}

def run_inference(image_bytes: bytes) -> tuple[dict, bytes]:
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

          # Draw box on image
        color = SEVERITY_COLORS.get(severity, (255, 255, 255))
        cv2.rectangle(img, (int(x1), int(y1)), (int(x2), int(y2)), color, 3)

        label = f"{disease_name} {confidence}% ({severity})"
        (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
        cv2.rectangle(img, (int(x1), int(y1) - lh - 10), (int(x1) + lw, int(y1)), color, -1)
        cv2.putText(img, label, (int(x1), int(y1) - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    if not detections:
        status = "healthy"
    else:
        detections.sort(key=lambda d: d["confidence"], reverse=True)
        status = "diseased"

    # Encode annotated image to bytes
    _, buffer = cv2.imencode(".jpg", img)
    annotated_bytes = buffer.tobytes()

    result = {"status": status, "detections": detections}
    return result, annotated_bytes
    