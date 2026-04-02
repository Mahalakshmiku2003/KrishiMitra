"""
scheduler.py
"""

import asyncio
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from services.whatsapp_service import send_proactive_message
from services.market_service import get_latest_prices
from services.db import SessionLocal
from scripts.scrape_karnataka_napanta import run as run_karnataka_scraper

scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")
_executor = ThreadPoolExecutor(max_workers=1)


async def morning_briefing():
    print(f"[Scheduler] Running morning briefing — {datetime.now()}")
    farmers = _get_all_farmers()

    for farmer in farmers:
        try:
            name     = farmer.get("name", "Kisan bhai")
            location = farmer.get("location", "India")
            crops    = farmer.get("crops", [])

            price_line = ""
            if crops:
                crop = crops[0]
                db = SessionLocal()
                try:
                    prices = get_latest_prices(crop, location, db)
                finally:
                    db.close()
                if prices:
                    p = prices[0]
                    price_line = f"{crop}: ₹{p['modal_price']}/quintal at {p['market']}."
                else:
                    price_line = f"Aaj {crop} ka bhav fetch ho raha hai."

            msg = (
                f"Subah ki salaam {name} bhai! 🌾\n"
                f"Aaj {location} mein mausam: theek hai, kaam karne ka accha din.\n"
                f"{price_line}\n"
                f"Koi bhi sawaal ho — bas photo ya message bhejein!"
            )
            await send_proactive_message(farmer["phone"], msg)

        except Exception as e:
            print(f"[Scheduler] Failed briefing for {farmer.get('phone')}: {e}")

    print(f"[Scheduler] Morning briefing done. Sent to {len(farmers)} farmers.")


async def daily_karnataka_scrape():
    print(f"[Scheduler] Running Karnataka scrape — {datetime.now()}")
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(_executor, run_karnataka_scraper)
        print("[Scheduler] Karnataka scrape completed.")
    except Exception as e:
        print(f"[Scheduler] Karnataka scrape failed: {e}")


def schedule_followup(phone: str, farmer_name: str, disease_name: str, bbox_pct: float):
    followup_date = datetime.now() + timedelta(days=3)
    job_id = f"followup_{phone}_{int(datetime.now().timestamp())}"
    scheduler.add_job(
        _send_followup,
        trigger="date",
        run_date=followup_date,
        args=[phone, farmer_name, disease_name, bbox_pct],
        id=job_id,
        replace_existing=True,
    )
    print(f"[Scheduler] Follow-up scheduled for {phone} on {followup_date.date()}")


async def _send_followup(phone: str, farmer_name: str, disease_name: str, bbox_pct: float):
    msg = (
        f"{farmer_name} bhai, 3 din pehle aapki fasal mein "
        f"{disease_name} thi ({bbox_pct}% affected).\n"
        f"Kya dawai laga di? Aur ab kaisa lag raha hai?\n"
        f"Ek nayi photo bhejein — main dekh leta hoon. 📸"
    )
    await send_proactive_message(phone, msg)
    print(f"[Scheduler] Follow-up sent to {phone} for {disease_name}")


def _get_all_farmers() -> list:
    from sqlalchemy import text
    with SessionLocal() as db:
        rows = db.execute(
            text("SELECT phone, name, crops, location FROM farmers")
        ).fetchall()
    return [
        {
            "phone":    row[0],
            "name":     row[1] or "Kisan bhai",
            "crops":    row[2] or [],
            "location": row[3] or "India",
        }
        for row in rows
    ]


def start_scheduler():
    """Register all jobs then start. Call this from main.py startup."""
    if scheduler.running:
        return

    scheduler.add_job(
        morning_briefing,
        trigger="cron",
        hour=7, minute=0,
        id="morning_briefing_job",
        replace_existing=True,
    )
    scheduler.add_job(
        daily_karnataka_scrape,
        trigger="cron",
        hour=8, minute=20,
        id="daily_karnataka_scrape",
        replace_existing=True,
    )

    scheduler.start()

    print("[Scheduler] Started. Registered jobs:")
    for job in scheduler.get_jobs():
        print(f"  {job.id} → next run: {job.next_run_time}")

