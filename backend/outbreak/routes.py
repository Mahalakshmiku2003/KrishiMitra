from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from outbreak.service import handle_new_detection
from services.db import get_db
from sqlalchemy import text  # ← missing this import
router = APIRouter()


@router.post("/new-detection")
async def new_detection(data: dict, db: Session = Depends(get_db)):
    """
    This will be called after AI detects disease
    """

    # 1️⃣ Save detection
    db.execute(text("""
        INSERT INTO detections
        (phone, disease_name, crop_type, severity, lat, lng, spread)
        VALUES (:phone, :disease_name, :crop_type, :severity, :lat, :lng, :spread)
    """), data)

    db.commit()

    # 2️⃣ Trigger outbreak logic
    result = await handle_new_detection(db, data)

    return {
        "status": "saved",
        "outbreak_result": result
    }