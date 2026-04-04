import uuid, os, logging, base64
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse

from services.image_utils import compress_image
from services.yolo_service import run_inference
from agent.diagnose import diagnose_image as agent_diagnose
from database import save_diagnosis
from config import UPLOAD_DIR, CLASSIFIER_PATH, DETECTOR_PATH

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
        # 🧪 Use specialized ONNX models from stitch/ for diagnosis
        agent_result = agent_diagnose(filepath, crop_type=crop_type)
        
        # 📸 Still run YOLO for bounding box visualization on the UI
        yolo_result, annotated_bytes = run_inference(compressed)
        
        # Merge results: Use Agent names, but YOLO for bbox if status is diseased
        merged_detections = []
        if not agent_result.get("error") and agent_result.get("raw_name") != "healthy":
            # 🚨 FIX: Pass raw float for confidence (0-1) so frontend can multiply by 100
            merged_detections.append({
                "disease":    agent_result["disease"],
                "confidence": agent_result["confidence_num"], # Raw float 0.0-1.0
                "severity":   agent_result["severity"]["level"],
                "remedies":   agent_result["remedies"],
                "urgency":    agent_result["urgency"],
                "pathogen":   agent_result["pathogen"],
                "symptoms":   agent_result["symptoms"],
                # Use YOLO's first box if available
                "bbox": yolo_result["detections"][0]["bbox"] if yolo_result["detections"] else None
            })
        
        final_status = "diseased" if merged_detections else "healthy"
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference failed: {e}")

    if merged_detections:
        top = merged_detections[0]
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

    return JSONResponse(content={
        "status":           final_status,
        "detections":       merged_detections,
        "annotated_image":  base64.b64encode(annotated_bytes).decode("utf-8"),
        "agent_analysis":   agent_result
    })