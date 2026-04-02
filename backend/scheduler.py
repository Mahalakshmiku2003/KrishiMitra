"""
backend/scheduler.py

Merge note: theirs was an __init__-style re-export shim, not the real
scheduler. This is the real scheduler (ours), unchanged except the
send_morning_briefings alias is exposed so backend/agent/whatsapp.py
can import it as before.
"""

import asyncio
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from services.whatsapp_service import send_proactive_message
from services.market_service import get_latest_prices
from services.db import SessionLocal
from backend.scripts.scrape_karnataka_napanta import run as run_karnataka_scraper

scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")
_executor = ThreadPoolExecutor(max_workers=1)


async def morning_briefing():
    print(f"[Scheduler] Running morning briefing — {datetime.now()}")
    farmers = _get_all_farmers()

    for farmer in farmers:
        try:
            name = farmer.get("name", "Kisan bhai")
            location = farmer.get("location", "India")
            crops = farmer.get("crops", [])

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
                    price_line = (
                        f"{crop}: ₹{p['modal_price']}/quintal at {p['market']}."
                    )
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


# Alias so whatsapp.py can import send_morning_briefings directly
send_morning_briefings = morning_briefing


async def daily_karnataka_scrape():
    print(f"[Scheduler] Running Karnataka scrape — {datetime.now()}")
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(_executor, run_karnataka_scraper)
        print("[Scheduler] Karnataka scrape completed.")
    except Exception as e:
        print(f"[Scheduler] Karnataka scrape failed: {e}")

async def check_price_alerts():
    """
    Runs every hour.
    For each active alert, checks prices at mandis NEAR that farmer.
    Only fires if the farmer's nearest mandi crosses the threshold.
    """
    from farmer_store import get_active_alerts, deactivate_alert, get_farmer_location
    from services.market_service import find_best_mandi_for_commodity

    alerts = get_active_alerts()
    if not alerts:
        print("[Alerts] No active alerts to check.")
        return

    print(f"[Alerts] Checking {len(alerts)} alerts...")
    db = SessionLocal()

    try:
        for alert in alerts:
            phone     = alert["phone"]
            commodity = alert["commodity"]

            # Get farmer's saved location
            location = get_farmer_location(phone)

            if location:
                # Check price at nearest mandi to farmer
                mandis = find_best_mandi_for_commodity(
                    farmer_lat=location["lat"],
                    farmer_lng=location["lng"],
                    commodity=commodity,
                    radius_km=300,
                    top_n=1,
                    db=db,
                )
                if not mandis:
                    print(f"[Alerts] No nearby mandi data for {phone} / {commodity}")
                    continue

                nearest       = mandis[0]
                current_price = nearest["modal_price"]
                market_name   = nearest["market"]
                distance_km   = nearest["distance_km"]

            else:
                # Farmer has no saved location — skip, can't check meaningfully
                print(f"[Alerts] No location for {phone}, skipping alert")
                continue

            # Check if threshold crossed
            triggered = (
                alert["direction"] == "above" and current_price >= alert["target_price"]
                or
                alert["direction"] == "below" and current_price <= alert["target_price"]
            )

            print(
                f"[Alerts] {phone} | {commodity} | "
                f"current=Rs.{current_price} | "
                f"target={alert['direction']} Rs.{alert['target_price']} | "
                f"triggered={triggered}"
            )

            if triggered:
                direction_word = "upar" if alert["direction"] == "above" else "neeche"
                msg = (
                    f"🔔 *Price Alert!*\n\n"
                    f"*{commodity.title()}* ab Rs.*{current_price}*/quintal hai\n"
                    f"Paas ka mandi: *{market_name}* ({distance_km}km)\n\n"
                    f"Aapka target tha: Rs.{alert['target_price']} se {direction_word}\n\n"
                    f"✅ Ab bechne ka sahi waqt! 🌾"
                )
                await send_proactive_message(phone, msg)
                deactivate_alert(alert["id"])
                print(f"[Alerts] ✅ Fired and deactivated for {phone}")

    finally:
        db.close()

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


async def _send_followup(
    phone: str, farmer_name: str, disease_name: str, bbox_pct: float
):
    msg = (
        f"{farmer_name} bhai, 3 din pehle aapki fasal mein "
        f"{disease_name} thi ({bbox_pct}% affected).\n"
        f"Kya dawai laga di? Aur ab kaisa lag raha hai?\n"
        f"Ek nayi photo bhejein — main dekh leta hoon. 📷"
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
            "phone": row[0],
            "name": row[1] or "Kisan bhai",
            "crops": row[2] or [],
            "location": row[3] or "India",
        }
        for row in rows
    ]


def start_scheduler():
    """Register all jobs then start. Called from main.py startup."""
    if scheduler.running:
        return

    scheduler.add_job(
        morning_briefing,
        trigger="cron",
        hour=7,
        minute=0,
        id="morning_briefing_job",
        replace_existing=True,
    )
    scheduler.add_job(
        daily_karnataka_scrape,
        trigger="cron",
        hour=8,
        minute=20,
        id="daily_karnataka_scrape",
        replace_existing=True,
    )
    scheduler.add_job(
        check_price_alerts,
        "cron", minute=0,       # every hour at :00
        id="price_alerts_job",
        replace_existing=True,
    )
    scheduler.start()

    print("[Scheduler] Started. Registered jobs:")
    for job in scheduler.get_jobs():
        print(f"  {job.id} → next run: {job.next_run_time}")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        print("[Scheduler] Stopped.")
