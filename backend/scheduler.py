"""
scheduler.py
"""

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from services.whatsapp_service import send_proactive_message
from services.market_service import get_latest_prices, find_best_mandi_for_commodity
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

def _organic_mild_lines(disease_name: str) -> str:
    db_path = Path(__file__).resolve().parent / "data" / "disease_db.json"
    if not db_path.exists():
        return (
            "  • Neem oil spray (subah jaldi)\n"
            "  • Prabhavit patte hatakar jal mein mila dein\n"
            "  • Poudhon ke beech hawa ka raasta rakhein"
        )
    data = json.loads(db_path.read_text(encoding="utf-8"))
    dn = disease_name.lower()
    for key, val in data.items():
        if dn in key.lower() or key.lower() in dn:
            org = (val.get("remedies") or {}).get("organic") or []
            pick = org[:4] if org else [
                "Neem oil / neem leaf extract — halka spray",
                "Infected leaves hata dein",
                "Paani ka jamav na hone dein",
            ]
            return "\n".join(f"  • {line}" for line in pick)
    return (
        "  • Neem-based spray (dose: dukaan / krishi kendra se puchein)\n"
        "  • Gunkari pattiyan alag karein\n"
        "  • Yadi halat gambhir ho to najdeeki krishi kendra jayein"
    )


def _buy_links(disease_name: str) -> str:
    q = quote_plus(f"{disease_name} agricultural fungicide pesticide India")
    return (
        "\n*Online khareed (udaharan / verify karke khareedein):*\n"
        f"• https://www.amazon.in/s?k={q}\n"
        f"• https://www.ugaoo.com/search?q={quote_plus(disease_name)}\n"
    )


async def send_disease_followup_round(
    phone: str, disease_name: str, crop_type: str, round_idx: int
):
    from farmer_store import normalize_phone, get_farmer, get_farmer_location

    tz = ZoneInfo("Asia/Kolkata")
    pid = normalize_phone(phone)
    prof = get_farmer(pid)
    name = (prof.get("name") or "Kisan bhai").split()[0]

    mild = _organic_mild_lines(disease_name)
    links = _buy_links(disease_name)

    mandi_line = ""
    loc = get_farmer_location(pid)
    if loc:
        db = SessionLocal()
        try:
            crop_key = (crop_type or "tomato").strip().lower()
            ms = find_best_mandi_for_commodity(
                farmer_lat=loc["lat"],
                farmer_lng=loc["lng"],
                commodity=crop_key,
                radius_km=500,
                top_n=2,
                db=db,
            )
            if ms:
                m0 = ms[0]
                mandi_line = (
                    f"\n\n*Paas ki mandi ({crop_key.title()}):*\n"
                    f"• {m0['market']}, {m0['state']} — "
                    f"Rs.{m0['modal_price']}/q (~{m0['distance_km']} km)"
                )
        finally:
            db.close()

    day_label = 2 * (round_idx + 1)
    msg = (
        f"Namaste {name} ji 🌾\n\n"
        f"*Follow-up* (din {day_label}): *{disease_name}* — fasl ab kaisi hai?\n"
        f"Agar theek ho gayi ho to bataiye; warna *nayi photo* bhejein 📸\n\n"
        f"*Halka / dekhbhal:*\n{mild}"
        f"{mandi_line}\n"
        f"{links}\n\n"
        f"Koi aur madad chahiye? 🌾"
    )
    await send_proactive_message(pid, msg)
    print(f"[Scheduler] Disease follow-up r{round_idx} → {pid}")

    if round_idx < 2:
        next_run = datetime.now(tz) + timedelta(days=2)
        nid = f"disease_fu_{pid}_{round_idx + 1}"
        scheduler.add_job(
            send_disease_followup_round,
            trigger="date",
            run_date=next_run,
            args=[pid, disease_name, crop_type, round_idx + 1],
            id=nid,
            replace_existing=True,
        )


def schedule_disease_followup_series(phone: str, disease_name: str, crop_type: str):
    from farmer_store import normalize_phone

    tz = ZoneInfo("Asia/Kolkata")
    pid = normalize_phone(phone)
    run_at = datetime.now(tz) + timedelta(days=2)
    jid = f"disease_fu_{pid}_0"
    scheduler.add_job(
        send_disease_followup_round,
        trigger="date",
        run_date=run_at,
        args=[pid, disease_name, crop_type, 0],
        id=jid,
        replace_existing=True,
    )
    print(f"[Scheduler] Disease follow-up series scheduled for {pid} @ {run_at}")


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
        hour=10, minute=20,
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

