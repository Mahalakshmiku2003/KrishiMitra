"""
scheduler.py  ← new file in backend/
Handles all scheduled/proactive messaging:
  - Daily 7am morning briefing to all farmers
  - 3-day follow-up after a disease diagnosis
"""

from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from services.whatsapp_service import send_proactive_message
from services.market_service import get_latest_prices
from services.db import SessionLocal

scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")


# ── Morning briefing — 7am every day ───────────────────────────────────────────

@scheduler.scheduled_job("cron", hour=7, minute=0)
async def morning_briefing():
    """Send daily farm update to every registered farmer."""
    print(f"[Scheduler] Running morning briefing — {datetime.now()}")
    farmers = _get_all_farmers()

    for farmer in farmers:
        try:
            name     = farmer.get("name", "Kisan bhai")
            location = farmer.get("location", "India")
            crops    = farmer.get("crops", [])

            # Build price snippet for farmer's first crop
            price_line = ""
            if crops:
                crop = crops[0]
                db   = SessionLocal()
                # Derive state from location (simple — use location as state name)
                prices = get_latest_prices(crop, location, db)
                db.close()
                if prices:
                    p          = prices[0]
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


# ── 3-day follow-up — scheduled at diagnosis time ──────────────────────────────

def schedule_followup(phone: str, farmer_name: str, disease_name: str, bbox_pct: float):
    """
    Call this right after a disease is diagnosed.
    Schedules a WhatsApp follow-up message 3 days later.

    Usage in agent.py or tools.py after a successful diagnosis:
        from scheduler import schedule_followup
        schedule_followup(phone, farmer['name'], disease_name, bbox_pct)
    """
    followup_date = datetime.now() + timedelta(days=3)
    job_id        = f"followup_{phone}_{int(datetime.now().timestamp())}"

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
    """The actual follow-up message sent 3 days after diagnosis."""
    msg = (
        f"{farmer_name} bhai, 3 din pehle aapki fasal mein "
        f"{disease_name} thi ({bbox_pct}% affected).\n"
        f"Kya dawai laga di? Aur ab kaisa lag raha hai?\n"
        f"Ek nayi photo bhejein — main dekh leta hoon. 📸"
    )
    await send_proactive_message(phone, msg)
    print(f"[Scheduler] Follow-up sent to {phone} for {disease_name}")


# ── Helper: fetch all farmers from DB ──────────────────────────────────────────

def _get_all_farmers() -> list:
    """Fetch all farmer records for the morning briefing."""
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