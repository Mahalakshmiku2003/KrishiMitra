import uuid, os, logging
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse

from services.image_utils import compress_image
from services.yolo_service import run_inference
from database import save_diagnosis
from config import UPLOAD_DIR

router = APIRouter()

@router.post("/diagnose")
async def diagnose_image(
    file:      UploadFile        = File(...),
    farmer_id: Optional[str]   = Form(None),
    crop_type: Optional[str]   = Form(None),
    gps_lat:   Optional[float] = Form(None),
    gps_lon:   Optional[float] = Form(None),
):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image.")

    raw_bytes = await file.read()
    if len(raw_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded.")

    try:
        compressed = compress_image(raw_bytes)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Image processing failed: {e}")

    filename = f"{uuid.uuid4()}.jpg"
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(compressed)

    try:
        result = run_inference(compressed)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference failed: {e}")

    if result["status"] == "diseased" and result["detections"]:
        top = result["detections"][0]
        try:
            save_diagnosis({
                "farmer_id":    farmer_id,
                "disease_name": top["disease"],
                "confidence":   top["confidence"],
                "severity":     top["severity"],
                "crop_type":    crop_type,
                "gps_lat":      gps_lat,
                "gps_lon":      gps_lon,
            })
        except Exception as db_err:
            logging.warning(f"DB save failed (non-fatal): {db_err}")

    return JSONResponse(content=result)  # ← inside the function, after the if block