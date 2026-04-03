import asyncio
import re
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import select, text

from backend.services.whatsapp_service import send_proactive_message
from backend.services.market_service import find_best_mandi_for_commodity
from backend.services.prediction_service import predict_prices_async
from backend.services.weather_service import get_weather

from backend.db.database import AsyncSessionLocal
from backend.db.models import Farmer

from backend.scripts.scrape_karnataka_napanta import run as run_karnataka_scraper


TRANSLATIONS = {
    "Hindi": {
        "greeting": "🌾 सुप्रभात!",
        "weather": "🌤 मौसम:",
        "temp": "तापमान",
        "humidity_label": "आर्द्रता",
        "rain": "वर्षा",
        "rain_yes": "हाँ / संभावना",
        "rain_no": "नहीं",
        "disease": "🦠 रोग:",
        "action": "💊 कार्रवाई:",
        "watering": "💧 सिंचाई:",
        "market": "💰 बाजार भाव:",
        "trend": "📈 भाव अनुमान:",
        "advice": "🌾 सलाह:",
        "monitor": "फसल की निगरानी करें और उपचार जारी रखें।",
        "humidity_warning": "अधिक आर्द्रता → फंगल रोग का खतरा। छिड़काव न करें।",
        "stable_weather": "मौसम स्थिर है → खेती के लिए अच्छा समय।",
        "check_prices": "बेचने से पहले मंडी भाव जांचें।",
        "safe_spray": "छिड़काव सुरक्षित है",
        "avoid_spray_rain": "बारिश के कारण छिड़काव न करೇं",
        "avoid_spray_humidity": "अधिक आर्द्रता के कारण छिड़काव न करें",
        "safe_water": "सिंचाई सुरक्षित है",
        "disease_detected": "रोग पाया गया:",
        "no_location_mand": "स्थानिक मंडी दरों के लिए लोकेशन साझा करें।",
    },
    "Kannada": {
        "greeting": "🌾 ಶುಭೋದಯ!",
        "weather": "🌤 ಹವಾಮಾನ:",
        "temp": "ತಾಪಮಾನ",
        "humidity_label": "ಆರ್ದ್ರತೆ",
        "rain": "ಮಳೆ",
        "rain_yes": "ಹೌದು / ಸಾಧ್ಯತೆ",
        "rain_no": "ಇಲ್ಲ",
        "disease": "🦠 ರೋಗ:",
        "action": "💊 ಕ್ರಮ:",
        "watering": "💧 ನೀರಾವರಿ:",
        "market": "💰 ಮಾರುಕಟ್ಟೆ ಬೆಲೆ:",
        "trend": "📈 ಬೆಲೆ ಅಂದಾಜು:",
        "advice": "🌾 ಸಲಹೆ:",
        "monitor": "ಬೆಳೆ ಗಮನಿಸಿ ಮತ್ತು ಚಿಕಿತ್ಸೆ ಮುಂದುವರಿಸಿ.",
        "humidity_warning": "ಹೆಚ್ಚು ಆರ್ದ್ರತೆ → ಹುಳು ರೋಗದ ಅಪಾಯ. ಸಿಂಪಡಣೆ ಬೇಡ.",
        "stable_weather": "ಹವಾಮಾನ ಸ್ಥಿರವಾಗಿದೆ → ಕೃಷಿಗೆ ಉತ್ತಮ ಸಮಯ.",
        "check_prices": "ಮಾರಾಟಕ್ಕೂ ಮೊದಲು ಮಾರುಕಟ್ಟೆ ಬೆಲೆ ಪರಿಶೀಲಿಸಿ.",
        "safe_spray": "ಸಿಂಪಡಣೆ ಸುರಕ್ಷಿತ",
        "avoid_spray_rain": "ಮಳೆಯ ಕಾರಣ ಸಿಂಪಡಣೆ ಬೇಡ",
        "avoid_spray_humidity": "ಹೆಚ್ಚು ಆರ್ದ್ರತೆ ಕಾರಣ ಸಿಂಪಡಣೆ ಬೇಡ",
        "safe_water": "ನೀರಾವರಿ ಸುರಕ್ಷಿತ",
        "disease_detected": "ರೋಗ ಪತ್ತೆಯಾಗಿದೆ:",
        "no_location_mand": "ಹತ್ತಿರದ ಮಂಡಿ ದರಗಳಿಗೆ ಲೊಕೇಶನ್ ಹಂಚಿಕೊಳ್ಳಿ.",
    },
    "English": {
        "greeting": "🌾 Good Morning!",
        "weather": "🌤 Weather:",
        "temp": "Temp",
        "humidity_label": "Humidity",
        "rain": "Rain",
        "rain_yes": "Yes / likely",
        "rain_no": "No",
        "disease": "🦠 Disease:",
        "action": "💊 Action:",
        "watering": "💧 Watering:",
        "market": "💰 Market prices:",
        "trend": "📈 Price outlook:",
        "advice": "🌾 Advice:",
        "monitor": "Monitor crop closely. Follow treatment schedule.",
        "humidity_warning": "High humidity → fungal risk. Avoid spraying.",
        "stable_weather": "Weather is stable → good for farming activities.",
        "check_prices": "Check mandi prices before selling.",
        "safe_spray": "Safe to spray",
        "avoid_spray_rain": "Avoid spraying (rain will wash it away)",
        "avoid_spray_humidity": "Avoid spraying (high humidity → fungal risk)",
        "safe_water": "Safe to water",
        "disease_detected": "Disease detected:",
        "no_location_mand": "Share your location for nearby mandi rates.",
    },
}


scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")
_executor = ThreadPoolExecutor(max_workers=1)


def _normalize_phone(phone: str) -> str:
    return (phone or "").replace("whatsapp:", "").strip().lower()


async def _get_all_farmers(db):
    result = await db.execute(select(Farmer))
    return result.scalars().all()


def _parse_weather_fields(weather_text: str) -> dict:
    t = weather_text or ""
    temp_m = re.search(r"Temperature:\s*([^\s,]+)", t)
    hum_m = re.search(r"Humidity:\s*([^\s,]+)", t)
    cond_m = re.search(r">\s*Condition:\s*(.+?)(?:\n|$)", t, re.I | re.S)
    if not cond_m:
        cond_m = re.search(r"Condition:\s*(.+?)(?:\n|$)", t, re.I)
    condition = (cond_m.group(1).strip() if cond_m else "") or "-"
    rain = bool(
        re.search(r"rain|drizzle|thunder|storm|shower|precip", t, re.I)
        or re.search(r"rain|drizzle|thunder|storm|shower", condition, re.I)
    )
    return {
        "temp": temp_m.group(1) if temp_m else "-",
        "humidity_str": hum_m.group(1) if hum_m else "-",
        "condition": condition,
        "rain": rain,
        "raw": t,
    }


async def _get_active_price_alerts(db):
    result = await db.execute(
        text(
            """
            SELECT id, phone, commodity, target_price, direction
            FROM price_alerts
            WHERE active = TRUE
            """
        )
    )
    rows = result.fetchall()
    return [
        {
            "id": r[0],
            "phone": (r[1] or "").strip().lower(),
            "commodity": r[2],
            "target_price": float(r[3]),
            "direction": r[4],
        }
        for r in rows
    ]


async def _deactivate_price_alert(db, alert_id: int):
    await db.execute(
        text("UPDATE price_alerts SET active = FALSE WHERE id = :id"),
        {"id": alert_id},
    )
    await db.commit()


async def _get_farmer_lat_lng(db, phone: str):
    phone = _normalize_phone(phone)
    if not phone:
        return None
    result = await db.execute(
        select(Farmer.lat, Farmer.lng).where(Farmer.phone == phone)
    )
    row = result.first()
    if row and row[0] is not None and row[1] is not None:
        return {"lat": float(row[0]), "lng": float(row[1])}
    return None


# ---------------- MORNING BRIEFING ----------------
async def morning_briefing():
    db = AsyncSessionLocal()
    try:
        farmers = await _get_all_farmers(db)

        for farmer in farmers:
            language = farmer.language or "Hindi"
            lang = TRANSLATIONS.get(language, TRANSLATIONS["English"])

            phone = _normalize_phone(farmer.phone)
            if not phone:
                continue

            lat = getattr(farmer, "lat", None)
            lng = getattr(farmer, "lng", None)
            crops = list(getattr(farmer, "crops", []) or [])

            messages: list[str] = []
            humidity = None
            rain = False
            weather_raw = None

            if lat is not None and lng is not None:
                weather_raw = await get_weather(float(lat), float(lng))
                parsed = _parse_weather_fields(weather_raw)
                rain = parsed["rain"]
                hum_match = re.search(r"([\d\.]+)", str(parsed["humidity_str"]) or "")
                if hum_match:
                    try:
                        humidity = float(hum_match.group(1))
                    except ValueError:
                        humidity = None

                messages.append(lang["weather"])
                temp_disp = str(parsed["temp"]).replace("°C", "").strip()
                messages.append(
                    f"• {lang['temp']}: {temp_disp}°C\n"
                    f"• {lang['humidity_label']}: {parsed['humidity_str']}\n"
                    f"• {lang['rain']}: {lang['rain_yes'] if rain else lang['rain_no']}\n"
                    f"• Sky: {parsed['condition']}"
                )
            else:
                messages.append(lang["weather"])
                messages.append(lang["no_location_mand"])

            disease = None
            if isinstance(farmer.last_detection, dict):
                disease = farmer.last_detection.get("disease")

            if disease:
                messages.append(
                    f"\n{lang['disease']}\n{lang['disease_detected']} {disease}"
                )

            spray_advice = "✅ " + lang["safe_spray"]
            water_advice = "💧 " + lang["safe_water"]

            if rain:
                spray_advice = "❌ " + lang["avoid_spray_rain"]
            elif humidity is not None and humidity >= 80:
                spray_advice = "⚠️ " + lang["avoid_spray_humidity"]

            if disease:
                from backend.agent.tools import get_treatment

                treatment = get_treatment(disease)
                spray_advice = f"💊 {treatment}"

                if humidity is not None and humidity >= 80:
                    spray_advice = "❌ " + lang["avoid_spray_humidity"]

            messages.append("\n" + lang["action"])
            messages.append(spray_advice)

            messages.append("\n" + lang["watering"])
            messages.append(water_advice)

            messages.append("\n" + lang["market"])
            if lat is not None and lng is not None and crops:
                for crop in crops:
                    mandis = await find_best_mandi_for_commodity(
                        farmer_lat=float(lat),
                        farmer_lng=float(lng),
                        commodity=crop,
                        radius_km=300,
                        top_n=1,
                        db=db,
                    )
                    if mandis:
                        m = mandis[0]
                        messages.append(
                            f"• {crop.title()} → ₹{m['modal_price']}/q @ {m['market']}"
                        )
                    else:
                        messages.append(f"• {crop.title()} → (no nearby mandi data)")
            elif crops:
                messages.append(lang["no_location_mand"])
            else:
                messages.append("• (no crops saved — tell us your crops in chat)")

            messages.append("\n" + lang["trend"])
            for crop in crops[:2]:
                pred = await predict_prices_async(crop, "default", db)
                if isinstance(pred, dict) and not pred.get("error"):
                    chg = pred.get("change_pct") or 0
                    messages.append(
                        f"• {crop.title()}: {pred.get('trend')} ({chg:+}%) — "
                        f"now ~₹{pred.get('current_price')}/q, "
                        f"7d est ~₹{pred.get('day_7_price')}/q"
                    )
                elif isinstance(pred, dict) and pred.get("error"):
                    messages.append(f"• {crop.title()}: {pred['error']}")

            final_advice = "\n" + lang["advice"] + "\n"

            if disease:
                final_advice += lang["monitor"] + "\n"

            if humidity is not None and humidity >= 80:
                final_advice += lang["humidity_warning"] + "\n"

            if not rain:
                final_advice += lang["stable_weather"] + "\n"

            final_advice += lang["check_prices"]

            messages.append(final_advice)

            final_message = lang["greeting"] + "\n\n" + "\n".join(messages)
            await send_proactive_message(phone, final_message)

    finally:
        await db.close()


async def send_morning_briefings():
    return await morning_briefing()


# ---------------- ALERTS ----------------
async def check_price_alerts():
    db = AsyncSessionLocal()
    try:
        alerts = await _get_active_price_alerts(db)
        if not alerts:
            return

        for alert in alerts:
            phone = alert["phone"]
            commodity = alert["commodity"]

            location = await _get_farmer_lat_lng(db, phone)
            if not location:
                continue

            mandis = await find_best_mandi_for_commodity(
                farmer_lat=location["lat"],
                farmer_lng=location["lng"],
                commodity=commodity,
                radius_km=300,
                top_n=1,
                db=db,
            )

            if not mandis:
                continue

            nearest = mandis[0]
            current_price = nearest["modal_price"]

            triggered = (
                alert["direction"] == "above" and current_price >= alert["target_price"]
            ) or (
                alert["direction"] == "below" and current_price <= alert["target_price"]
            )

            if triggered:
                msg = (
                    f"🔔 Price alert!\n"
                    f"{commodity.title()} is now Rs.{current_price}/quintal "
                    f"({alert['direction']} your target Rs.{alert['target_price']:.0f}).\n"
                    f"Mandi: {nearest['market']}"
                )
                await send_proactive_message(phone, msg)
                await _deactivate_price_alert(db, alert["id"])

    finally:
        await db.close()


# ---------------- SCRAPER ----------------
async def daily_karnataka_scrape():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(_executor, run_karnataka_scraper)


# ---------------- OUTBREAK ----------------
async def check_new_detections():
    try:
        from backend.outbreak.service import process_pending_detections

        await process_pending_detections()
    except Exception as e:
        print("Outbreak error:", e)


# ---------------- FOLLOW-UP ----------------
def schedule_followup(
    phone,
    farmer_name,
    disease_name,
    bbox_pct,
    severity=None,
):
    run_date = datetime.now() + timedelta(minutes=1)
    phone_n = _normalize_phone(phone)
    job_id = f"followup_{phone_n}_{int(datetime.now().timestamp() * 1000)}"

    scheduler.add_job(
        _send_followup,
        DateTrigger(run_date=run_date),
        args=[phone_n, farmer_name, disease_name, bbox_pct, severity],
        id=job_id,
        replace_existing=False,
        misfire_grace_time=3600,
    )


async def _send_followup(phone, farmer_name, disease_name, bbox_pct, severity=None):
    phone_n = _normalize_phone(phone)
    disease_label = disease_name or "your crop issue"
    msg = f"""
🌾 Follow-up Check

Earlier, your crop had *{disease_label}*

📊 Infection level: ~{bbox_pct}%

💊 Quick Treatment Plan:
• Apply recommended fungicide
• Remove affected leaves
• Avoid overwatering

👉 If treated:
Send a new photo to check progress

❓ Need more treatment information? Just ask!

Stay alert 🚜
"""
    await send_proactive_message(phone_n, msg.strip())


# ---------------- START ----------------
def start_scheduler():
    if scheduler.running:
        return

    scheduler.add_job(
        morning_briefing,
        CronTrigger(hour=6, minute=30),
        id="morning_briefing",
        replace_existing=True,
    )

    scheduler.add_job(
        check_price_alerts,
        "interval",
        minutes=15,
        id="price_alerts",
        replace_existing=True,
    )

    scheduler.add_job(
        daily_karnataka_scrape,
        CronTrigger(hour=2, minute=0),
        id="scraper",
        replace_existing=True,
    )

    scheduler.add_job(
        check_new_detections,
        "interval",
        minutes=10,
        id="outbreak_detections",
        replace_existing=True,
    )

    scheduler.start()
    print(
        "Scheduler started (morning_briefing, check_price_alerts, check_new_detections, "
        "daily_karnataka_scrape; schedule_followup registers follow-up jobs on demand)"
    )


def stop_scheduler():
    scheduler.shutdown()
    print("Scheduler stopped")
