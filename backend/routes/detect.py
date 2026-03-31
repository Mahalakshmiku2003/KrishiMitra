from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse
from PIL import Image
from services.yolo_service import get_model
from services.file_service import save_upload, cleanup

router = APIRouter()

@router.post("/")
async def detect(file: UploadFile = File(...)):
    """
    Step 1.
    Pass a plant image → get bounding boxes around diseased regions.
    Feed these boxes + image into your friend's classifier to get disease name.
    """
    tmp_path = save_upload(file)
    try:
        model        = get_model()
        img          = Image.open(tmp_path).convert("RGB")
        img_w, img_h = img.size
        results      = model(str(tmp_path), verbose=False)[0]

        if results.boxes is None or len(results.boxes) == 0:
            return JSONResponse({
                "status":     "no_detection",
                "message":    "No diseased region detected in this image.",
                "image_size": {"width": img_w, "height": img_h},
                "detections": []
            })

        detections = []
        for box in results.boxes:
            x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
            conf  = float(box.conf)
            label = model.names[int(box.cls)]

            detections.append({
                "yolo_label": label,
                "confidence": round(conf, 3),
                "bbox": {
                    "x1": x1, "y1": y1,
                    "x2": x2, "y2": y2,
                    "width":  x2 - x1,
                    "height": y2 - y1,
                },
                "bbox_pct": round(((x2 - x1) * (y2 - y1)) / (img_w * img_h) * 100, 1)
            })

        return JSONResponse({
            "status":     "detected",
            "image_size": {"width": img_w, "height": img_h},
            "total":      len(detections),
            "detections": detections
        })

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        cleanup(tmp_path)