from services.db import SessionLocal
from outbreak.service import handle_new_detection
from sqlalchemy import text
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

def start_scheduler():
    scheduler.start()

async def check_new_detections():
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT * FROM detections
            WHERE severity = 5 
            AND spread = true
            AND processed = false
        """)).mappings().all()

        print(f"🔍 Found {len(result)} unprocessed outbreaks")

        for row in result:
            print("🔥 Outbreak detected:", row["disease_name"])
            await handle_new_detection(db, dict(row))
            db.execute(text("UPDATE detections SET processed = true WHERE id = :id"), {"id": row["id"]})

        db.commit()
    finally:
        db.close()