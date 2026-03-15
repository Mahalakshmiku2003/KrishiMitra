from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from services.severity_service import calculate_severity, get_overall_severity
from services.disease_service import lookup_static

router = APIRouter()

class BBox(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int

class Detection(BaseModel):
    bbox:       BBox
    confidence: float

class SeverityRequest(BaseModel):
    disease_name: str
    image_size:   dict        # {"width": 640, "height": 480}
    detections:   list[Detection]   # paste directly from /detect response

@router.post("/")
async def severity(request: SeverityRequest):
    """
    Pass the detections array + image_size directly from /detect response.
    No image needed. No YOLO re-run. Pure math.

    Body:
    {
        "disease_name": "Tomato Early blight leaf",
        "image_size":   { "width": 640, "height": 480 },
        "detections": [
            {
                "bbox":       { "x1": 120, "y1": 80, "x2": 340, "y2": 290 },
                "confidence": 0.874
            }
        ]
    }
    """
    try:
        img_w = request.image_size.get("width")
        img_h = request.image_size.get("height")

        if not img_w or not img_h:
            return JSONResponse(
                status_code=422,
                content={"error": "image_size must have width and height"}
            )

        if not request.detections:
            return JSONResponse({
                "status":           "no_detection",
                "disease_name":     request.disease_name,
                "overall_severity": None,
                "message":          "No detections passed — cannot calculate severity."
            })

        db_entry   = lookup_static(request.disease_name) or {}
        results    = []

        for det in request.detections:
            bbox = [det.bbox.x1, det.bbox.y1, det.bbox.x2, det.bbox.y2]
            sev  = calculate_severity(bbox, img_w, img_h, det.confidence, db_entry)
            results.append({
                "bbox":     {"x1": det.bbox.x1, "y1": det.bbox.y1,
                             "x2": det.bbox.x2, "y2": det.bbox.y2},
                "severity": sev
            })

        return JSONResponse({
            "status":           "calculated",
            "disease_name":     request.disease_name,
            "overall_severity": get_overall_severity(results),
            "all_detections":   results,
        })

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})