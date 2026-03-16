def calculate_severity(box_area: float, image_area: float) -> str:
    ratio = box_area / image_area if image_area > 0 else 0
    if ratio < 0.20:
        return "Mild"
    elif ratio < 0.60:
        return "Moderate"
    return "Severe"