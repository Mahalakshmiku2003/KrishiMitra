from services.db import SessionLocal
from outbreak.service import handle_new_detection
from sqlalchemy import text
processed_ids = set()

async def check_new_detections():
    db = SessionLocal()

    try:
        result = db.execute(text("""
            SELECT * FROM detections
            WHERE severity = 5 
            AND spread = true
            AND processed = false
        """)).mappings().all()

        for row in result:
            if row["id"] in processed_ids:
                continue

            print("🔥 Outbreak detected:", row["disease_name"])

            detection = dict(row)

            await handle_new_detection(db, detection)

            db.execute(
                "UPDATE detections SET processed = true WHERE id = :id",
                {"id": row["id"]}
               )
            db.commit()

    finally:
        db.close()