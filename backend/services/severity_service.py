def calculate_severity(bbox, img_w, img_h, confidence, disease_entry={}):
    x1, y1, x2, y2 = bbox
    bbox_area  = max(0, (x2 - x1) * (y2 - y1))
    total_area = img_w * img_h
    bbox_pct   = (bbox_area / total_area) * 100 if total_area > 0 else 0

    thresholds = disease_entry.get("severity_thresholds", {"mild": 0.20, "moderate": 0.60})
    mild_t     = thresholds["mild"] * 100
    moderate_t = thresholds["moderate"] * 100

    if bbox_pct < mild_t:
        level = "Mild"
    elif bbox_pct < moderate_t:
        level = "Moderate"
    else:
        level = "Severe"

    if confidence > 0.85 and level == "Mild":
        level = "Moderate"

    descriptions = {
        "Mild":     f"{bbox_pct:.1f}% of leaf affected. Early stage.",
        "Moderate": f"{bbox_pct:.1f}% of leaf affected. Treat immediately.",
        "Severe":   f"{bbox_pct:.1f}% of leaf affected. Emergency response needed.",
    }
    colors = {
        "Mild":     "#F9A825",
        "Moderate": "#E65100",
        "Severe":   "#B71C1C",
    }

    return {
        "level":          level,
        "bbox_pct":       round(bbox_pct, 1),
        "confidence_pct": round(confidence * 100, 1),
        "description":    descriptions[level],
        "color":          colors[level],
    }


def get_overall_severity(detections: list) -> dict | None:
    if not detections:
        return None
    order   = {"Severe": 0, "Moderate": 1, "Mild": 2}
    worst   = min(detections, key=lambda x: order.get(x["severity"]["level"], 3))
    return worst["severity"]