from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse
from PIL import Image
from backend.services.yolo_service import get_model
from backend.services.severity_service import calculate_severity, get_overall_severity
from backend.services.disease_service import lookup_static, lookup_claude
from backend.services.file_service import save_upload, cleanup

router = APIRouter()

@router.post("/full")
async def diagnose_full(
    file:         UploadFile = File(...),
    disease_name: str        = Form(...),
    location:     str        = Form(default="India"),
    force_ai:     bool       = Form(default=False),
):
    """
    Combined endpoint.
    Runs YOLO once, reuses the bbox output for severity. No double inference.
    """
    tmp_path = save_upload(file)
    try:
        model        = get_model()
        img          = Image.open(tmp_path).convert("RGB")
        img_w, img_h = img.size

        # ── Run YOLO once ─────────────────────────────────────────────────────
        results  = model(str(tmp_path), verbose=False)[0]
        db_entry = lookup_static(disease_name) or {}

        # ── Reuse bbox output directly for severity — no second YOLO run ──────
        detections = []
        if results.boxes is not None and len(results.boxes) > 0:
            for box in results.boxes:
                bbox = [int(v) for v in box.xyxy[0].tolist()]
                conf = float(box.conf)
                sev  = calculate_severity(bbox, img_w, img_h, conf, db_entry)
                detections.append({
                    "bbox": {
                        "x1": bbox[0], "y1": bbox[1],
                        "x2": bbox[2], "y2": bbox[3]
                    },
                    "yolo_confidence": round(conf, 3),
                    "severity":        sev,
                })

        # ── Treatment info ────────────────────────────────────────────────────
        treatment_info = None
        source         = None

        if not force_ai:
            entry = lookup_static(disease_name)
            if entry:
                treatment_info = entry
                source         = "static_db"

        if treatment_info is None:
            treatment_info = lookup_claude(disease_name, location)
            source         = "claude_api"

        # ── Response ──────────────────────────────────────────────────────────
        return JSONResponse({
            "status":       "success",
            "disease_name": disease_name,
            "display_name": treatment_info.get("display_name", disease_name),
            "crop":         treatment_info.get("crop", "Unknown"),
            "source":       source,

            "detection": {
                "total_boxes":      len(detections),
                "overall_severity": get_overall_severity(detections),
                "boxes":            detections,
                "image_size":       {"width": img_w, "height": img_h},
            },

            "disease_info": {
                "pathogen":      treatment_info.get("pathogen", ""),
                "symptoms":      treatment_info.get("symptoms", ""),
                "spread":        treatment_info.get("spread", ""),
                "urgency":       treatment_info.get("urgency", ""),
                "regional_note": treatment_info.get("regional_note", ""),
                "remedies":      treatment_info.get("remedies", {
                    "organic": [], "chemical": [], "prevention": []
                }),
            }
        })

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        cleanup(tmp_path)
