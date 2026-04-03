import asyncio
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import select

from backend.services.whatsapp_service import send_proactive_message
from backend.services.market_service import find_best_mandi_for_commodity
from backend.services.prediction_service import predict_prices
from backend.services.weather_service import get_weather

from backend.db.database import AsyncSessionLocal
from backend.db.models import Farmer

from backend.scripts.scrape_karnataka_napanta import run as run_karnataka_scraper


TRANSLATIONS = {
    "Hindi": {
        "greeting": "🌾 सुप्रभात!",
        "weather": "🌤 मौसम:",
        "disease": "🦠 रोग:",
        "action": "💊 कार्रवाई:",
        "watering": "💧 सिंचाई:",
        "market": "💰 बाजार भाव:",
        "trend": "📈 रुझान:",
        "advice": "👉 सलाह:",
        "monitor": "फसल की निगरानी करें और उपचार जारी रखें।",
        "humidity_warning": "अधिक आर्द्रता → फंगल रोग का खतरा। छिड़काव न करें।",
        "stable_weather": "मौसम स्थिर है → खेती के लिए अच्छा समय।",
        "check_prices": "बेचने से पहले मंडी भाव जांचें।",
        "safe_spray": "छिड़काव सुरक्षित है",
        "avoid_spray_rain": "बारिश के कारण छिड़काव न करें",
        "avoid_spray_humidity": "अधिक आर्द्रता के कारण छिड़काव न करें",
        "safe_water": "सिंचाई सुरक्षित है",
        "disease_detected": "रोग पाया गया:",
    },
    "Kannada": {
        "greeting": "🌾 ಶುಭೋದಯ!",
        "weather": "🌤 ಹವಾಮಾನ:",
        "disease": "🦠 ರೋಗ:",
        "action": "💊 ಕ್ರಮ:",
        "watering": "💧 ನೀರಾವರಿ:",
        "market": "💰 ಮಾರುಕಟ್ಟೆ ಬೆಲೆ:",
        "trend": "📈 ಪ್ರವೃತ್ತಿ:",
        "advice": "👉 ಸಲಹೆ:",
        "monitor": "ಬೆಳೆ ಗಮನಿಸಿ ಮತ್ತು ಚಿಕಿತ್ಸೆ ಮುಂದುವರಿಸಿ.",
        "humidity_warning": "ಹೆಚ್ಚು ಆರ್ದ್ರತೆ → ಹುಳು ರೋಗದ ಅಪಾಯ. ಸಿಂಪಡಣೆ ಬೇಡ.",
        "stable_weather": "ಹವಾಮಾನ ಸ್ಥಿರವಾಗಿದೆ → ಕೃಷಿಗೆ ಉತ್ತಮ ಸಮಯ.",
        "check_prices": "ಮಾರಾಟಕ್ಕೂ ಮೊದಲು ಮಾರುಕಟ್ಟೆ ಬೆಲೆ ಪರಿಶೀಲಿಸಿ.",
        "safe_spray": "ಸಿಂಪಡಣೆ ಸುರಕ್ಷಿತ",
        "avoid_spray_rain": "ಮಳೆಯ ಕಾರಣ ಸಿಂಪಡಣೆ ಬೇಡ",
        "avoid_spray_humidity": "ಹೆಚ್ಚು ಆರ್ದ್ರತೆ ಕಾರಣ ಸಿಂಪಡಣೆ ಬೇಡ",
        "safe_water": "ನೀರಾವರಿ ಸುರಕ್ಷಿತ",
        "disease_detected": "ರೋಗ ಪತ್ತೆಯಾಗಿದೆ:",
    },
    "English": {
        "greeting": "🌾 Good Morning!",
        "weather": "🌤 Weather:",
        "disease": "🦠 Disease:",
        "action": "💊 Action:",
        "watering": "💧 Watering:",
        "market": "💰 Market Prices:",
        "trend": "📈 Trend:",
        "advice": "👉 Advice:",
        "monitor": "Monitor crop closely. Follow treatment schedule.",
        "humidity_warning": "High humidity → fungal risk. Avoid spraying.",
        "stable_weather": "Weather is stable → good for farming activities.",
        "check_prices": "Check mandi prices before selling.",
        "safe_spray": "Safe to spray",
        "avoid_spray_rain": "Avoid spraying (rain will wash it away)",
        "avoid_spray_humidity": "Avoid spraying (high humidity → fungal risk)",
        "safe_water": "Safe to water",
        "disease_detected": "Disease detected:",
    },
}


scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")
_executor = ThreadPoolExecutor(max_workers=1)


async def _get_all_farmers(db):
    result = await db.execute(select(Farmer))
    return result.scalars().all()


# ---------------- MORNING BRIEFING ----------------
async def morning_briefing():
    db = AsyncSessionLocal()
    try:
        farmers = await _get_all_farmers(db)

        for farmer in farmers:
            language = getattr(farmer, "language", "English")
            lang = TRANSLATIONS.get(language, TRANSLATIONS["English"])

            phone = farmer.phone
            lat = getattr(farmer, "lat", None)
            lng = getattr(farmer, "lng", None)
            crops = getattr(farmer, "crops", []) or []

            messages = []

            weather_text = None
            humidity = None
            rain = False

            if lat and lng:
                weather_text = await get_weather(lat, lng)
                w = (weather_text or "").lower()

                import re

                h_match = re.search(r"humidity[:\s]*([\d\.]+)", w)
                if h_match:
                    humidity = float(h_match.group(1))

                rain = any(x in w for x in ["rain", "drizzle", "storm"])

                messages.append(lang["weather"])
                messages.append(weather_text)

            disease = None
            if hasattr(farmer, "last_detection") and isinstance(
                farmer.last_detection, dict
            ):
                disease = farmer.last_detection.get("disease")

            if disease:
                messages.append(
                    f"\n{lang['disease']}\n{lang['disease_detected']} {disease}"
                )

            spray_advice = "✅ " + lang["safe_spray"]
            water_advice = "💧 " + lang["safe_water"]

            if rain:
                spray_advice = "❌ " + lang["avoid_spray_rain"]
            elif humidity and humidity >= 80:
                spray_advice = "⚠️ " + lang["avoid_spray_humidity"]

            if disease:
                from backend.agent.tools import get_treatment

                treatment = get_treatment(disease)
                spray_advice = f"💊 {treatment}"

                if humidity and humidity >= 80:
                    spray_advice = "❌ " + lang["avoid_spray_humidity"]

            messages.append("\n" + lang["action"])
            messages.append(spray_advice)

            messages.append("\n" + lang["watering"])
            messages.append(water_advice)

            messages.append("\n" + lang["market"])

            for crop in crops:
                mandis = await find_best_mandi_for_commodity(
                    farmer_lat=lat,
                    farmer_lng=lng,
                    commodity=crop,
                    radius_km=300,
                    top_n=1,
                    db=db,
                )

                if mandis:
                    m = mandis[0]
                    messages.append(
                        f"{crop.title()} → ₹{m['modal_price']} ({m['market']})"
                    )

            messages.append("\n" + lang["trend"])

            for crop in crops[:2]:
                pred = predict_prices(crop, None, db)
                if isinstance(pred, dict) and not pred.get("error"):
                    messages.append(
                        f"{crop.title()} → {pred.get('trend')} ({pred.get('change_pct')}%)"
                    )

            final_advice = "\n" + lang["advice"] + "\n"

            if disease:
                final_advice += lang["monitor"] + "\n"

            if humidity and humidity >= 80:
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
    from backend.farmer_store import (
        get_active_alerts,
        deactivate_alert,
        get_farmer_location,
    )

    alerts = get_active_alerts()
    if not alerts:
        return

    db = AsyncSessionLocal()
    try:
        for alert in alerts:
            phone = alert["phone"]
            commodity = alert["commodity"]

            location = get_farmer_location(phone)
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
                    f"🔔 Price Alert!\n"
                    f"{commodity} is now Rs.{current_price}/quintal\n"
                    f"Mandi: {nearest['market']}"
                )
                await send_proactive_message(phone, msg)
                deactivate_alert(alert["id"])

    finally:
        await db.close()


# ---------------- SCRAPER ----------------
async def daily_karnataka_scrape():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(_executor, run_karnataka_scraper)


# ---------------- FOLLOW-UP ----------------
def schedule_followup(phone, farmer_name, disease_name, bbox_pct):
    run_date = datetime.now() + timedelta(days=3)

    scheduler.add_job(
        _send_followup,
        trigger="date",
        run_date=run_date,
        args=[phone, farmer_name, disease_name, bbox_pct],
        id=f"followup_{phone}_{int(datetime.now().timestamp())}",
        replace_existing=True,
    )


async def _send_followup(phone, farmer_name, disease_name, bbox_pct):
    msg = (
        f"{farmer_name}, your crop had {disease_name} ({bbox_pct}%).\n"
        f"Did you apply treatment? Send a new photo."
    )
    await send_proactive_message(phone, msg)


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

    scheduler.start()
    print("Scheduler started")


def stop_scheduler():
    scheduler.shutdown()
    print("Scheduler stopped")
