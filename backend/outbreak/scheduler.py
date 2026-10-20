import asyncio
from services.db import SessionLocal
from outbreak.service import handle_new_detection
from sqlalchemy import text
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

def start_scheduler():
    scheduler.start()

def _fetch_unprocessed_outbreaks():
    with SessionLocal() as db:
        return db.execute(text("""
            SELECT * FROM detections
            WHERE severity > 5
            AND spread = true
            AND processed = false
        """)).mappings().all()

def _mark_detection_processed(detection_id: int):
    with SessionLocal() as db:
        db.execute(text("UPDATE detections SET processed = true WHERE id = :id"), {"id": detection_id})
        db.commit()

async def check_new_detections():
    result = await asyncio.to_thread(_fetch_unprocessed_outbreaks)
    if not result:
        return

    print(f"🔍 Found {len(result)} unprocessed outbreaks")

    with SessionLocal() as db:
        for row in result:
            print("🔥 Outbreak detected:", row["disease_name"])
            await handle_new_detection(db, dict(row))
            await asyncio.to_thread(_mark_detection_processed, row["id"])