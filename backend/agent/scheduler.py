import asyncio
import os
import re
import time
from datetime import datetime
from typing import Any

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
from sqlalchemy import select
from twilio.rest import Client

from backend.agent.agent import client as groq_client
from backend.agent.tools import get_mandi_price_from_db, get_treatment
from backend.db.crud import get_farmer_profile
from backend.db.deps import get_db
from backend.db.models import Farmer

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
OPENWEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"

DEFAULT_WEATHER = {
    "temp": 30.0,
    "humidity": 50.0,
    "rain": 0.0,
    "wind": 5.0,
}
WEATHER_CACHE_TTL = 1800
weather_cache: dict[str, tuple[dict[str, float], float]] = {}
http_client = httpx.AsyncClient(timeout=10.0)

twilio_client = (
    Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN
    else None
)


def _safe_float(value: Any, fallback: float) -> float:
    try:
        if value is None:
            return fallback
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _extract_metric(pattern: str, text: str, fallback: float) -> float:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return fallback
    return _safe_float(match.group(1), fallback)


def normalize_weather_data(weather_result: Any) -> dict[str, float]:
    if isinstance(weather_result, dict):
        return {
            "temp": _safe_float(weather_result.get("temp"), DEFAULT_WEATHER["temp"]),
            "humidity": _safe_float(
                weather_result.get("humidity"), DEFAULT_WEATHER["humidity"]
            ),
            "rain": _safe_float(weather_result.get("rain"), DEFAULT_WEATHER["rain"]),
            "wind": _safe_float(weather_result.get("wind"), DEFAULT_WEATHER["wind"]),
        }

    weather_text = str(weather_result or "")
    return {
        "temp": _extract_metric(
            r"temperature\s*[:=]\s*(-?\d+(?:\.\d+)?)",
            weather_text,
            DEFAULT_WEATHER["temp"],
        ),
        "humidity": _extract_metric(
            r"humidity\s*[:=]\s*(\d+(?:\.\d+)?)",
            weather_text,
            DEFAULT_WEATHER["humidity"],
        ),
        "rain": _extract_metric(
            r"(?:rain|precipitation)(?:\s+chance)?\s*[:=]\s*(\d+(?:\.\d+)?)",
            weather_text,
            DEFAULT_WEATHER["rain"],
        ),
        "wind": _extract_metric(
            r"wind(?:\s+speed)?\s*[:=]\s*(\d+(?:\.\d+)?)",
            weather_text,
            DEFAULT_WEATHER["wind"],
        ),
    }
async def fetch_weather_api(location: str) -> dict[str, float]:
    print(f"🌤️ Fetching weather for: {location}")
    key = location.strip().lower()
    cached_weather = weather_cache.get(key)
    if cached_weather:
        cached_data, cached_at = cached_weather
        if time.time() - cached_at < WEATHER_CACHE_TTL:
            return cached_data

    if not OPENWEATHER_API_KEY:
        print(
            "OpenWeather API key not configured. Falling back to default weather data."
        )
        return normalize_weather_data(DEFAULT_WEATHER)

    for attempt in range(2):
        try:
            print("➡️ Calling OpenWeather API")
            try:
                response = await http_client.get(
                    OPENWEATHER_URL,
                    params={
                        "q": location,
                        "appid": OPENWEATHER_API_KEY,
                        "units": "metric",
                    },
                )
            except Exception as e:
                print("❌ ERROR in weather API:", e)
                raise
            response.raise_for_status()
            print("✅ Weather API success")
            payload = response.json()

            parsed_weather = normalize_weather_data(
                {
                    "temp": payload.get("main", {}).get("temp"),
                    "humidity": payload.get("main", {}).get("humidity"),
                    "rain": payload.get("rain", {}).get("1h", 0.0),
                    "wind": payload.get("wind", {}).get("speed"),
                }
            )
            if len(weather_cache) > 100:
                weather_cache.clear()
            weather_cache[key] = (parsed_weather, time.time())
            return parsed_weather
        except Exception as e:
            print(f"Weather API issue or invalid location: {location}")
            print(
                f"OpenWeather fetch failed for {location} on attempt {attempt + 1}: {e}"
            )
            if attempt == 1:
                return normalize_weather_data(DEFAULT_WEATHER)


async def close_http_client():
    await http_client.aclose()


def analyze_farming_conditions(
    weather: dict[str, Any], disease: str | None, crops: list[str] | None
) -> dict[str, str]:
    humidity = _safe_float(weather.get("humidity"), DEFAULT_WEATHER["humidity"])
    rain = _safe_float(weather.get("rain"), DEFAULT_WEATHER["rain"])
    wind = _safe_float(weather.get("wind"), DEFAULT_WEATHER["wind"])
    hour = datetime.now().hour
    crop_names = [str(crop).strip().lower() for crop in (crops or []) if crop]

    advice = {
        "watering": "\u2705 Safe to water today",
        "spray": "No spray needed today",
    }

    if rain > 2:
        advice["watering"] = "\u274c Do not water (rain expected)"
        advice["spray"] = "\u274c Do not spray (will wash away)"
        return advice

    if humidity > 80:
        advice["watering"] = "\u26a0\ufe0f Avoid watering (high humidity)"

    if "rice" in crop_names:
        advice["watering"] = "\u2705 Maintain standing water (rice crop)"

    if humidity > 85:
        advice["extra"] = "\u26a0\ufe0f High fungal spread risk today"

    if humidity > 85 and rain == 0:
        advice["confidence"] = "\u26a0\ufe0f High disease spread risk today"

    if not disease:
        advice["spray"] = "No disease detected, no spray needed"
        return advice

    if "tomato" in crop_names and humidity > 75:
        advice["spray"] = "\u26a0\ufe0f High fungal risk for tomato"
    elif humidity > 85 or wind > 20:
        advice["spray"] = "\u274c Avoid spraying (bad conditions)"
    else:
        advice["spray"] = "\u2705 Spray early morning (5-8 AM)"

    if hour > 9:
        advice["spray"] += " (kal subah karein)"

    return advice


async def send_whatsapp(to: str, message: str, retries: int = 3):
    if not twilio_client:
        print(f"Twilio client not configured. Unable to send message to {to}.")
        return

    for attempt in range(retries):
        try:
            await asyncio.to_thread(
                twilio_client.messages.create,
                from_=TWILIO_WHATSAPP_NUMBER,
                to=to,
                body=message,
            )

            print(f"Sent to {to}")
            return

        except Exception as e:
            print(f"Retry {attempt + 1} failed for {to}: {e}")
            if attempt < retries - 1:
                await asyncio.sleep(2)

    print(f"Failed to send to {to} after retries")


async def generate_briefing(db, farmer_id: str) -> str:
    try:
        profile = await get_farmer_profile(db, farmer_id)

        farmer = profile["farmer"]
        crops = profile["crops"]
        recent_disease = profile["recent_disease"]

        if not farmer:
            return None

        location = (farmer.location or "").strip()
        language = farmer.language or "Hindi"

        if not location:
            print(f"Warning: skipping farmer {farmer_id} due to missing DB location")
            return None

        print(f"\nFarmer: {farmer_id}")
        print(f"  Location: {location}")
        print(f"  Crops: {crops}")
        print(f"  Disease: {recent_disease}")

        weather_data = await fetch_weather_api(location)
        print("🌤️ Weather Data:", weather_data)
        advice = analyze_farming_conditions(weather_data, recent_disease, crops)

        mandi_summary = ""
        if crops:
            try:
                first_crop = crops[0]
                mandi_price = await get_mandi_price_from_db(db, first_crop, location)
                mandi_summary = f"\nMandi price ({first_crop}): {mandi_price}"
                mandi_summary = mandi_summary[:200]
            except Exception as e:
                print(f"Failed to fetch mandi price for {farmer_id}: {e}")

        today = datetime.now().strftime("%A, %d %B %Y")
        spray_instruction = (
            "3. Spray advice (if disease exists)"
            if recent_disease
            else "3. Skip spray advice if there is no disease"
        )

        response = await groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You are KrishiMitra.\n\n"
                        f"Today is {today}, 8:00 AM.\n\n"
                        f"Reply in {language}.\n"
                        "Keep message SHORT (max 5 bullet points).\n"
                        "Use farmer-friendly language.\n"
                        "Start with a morning greeting.\n"
                        "Give clear actionable advice.\n"
                        "Include:\n"
                        "1. Weather summary\n"
                        "2. Watering advice\n"
                        f"{spray_instruction}\n"
                        "4. One clear action for today\n"
                        "End with one clear action only."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Location: {location}\n"
                        f"Crops: {', '.join(crops)}\n"
                        f"Disease: {recent_disease or 'None'}\n\n"
                        "Structured weather:\n"
                        f"Temp: {weather_data['temp']}\u00b0C\n"
                        f"Humidity: {weather_data['humidity']}%\n"
                        f"Rain: {weather_data['rain']} mm\n"
                        f"Wind: {weather_data['wind']} km/h\n\n"
                        "Advice:\n"
                        f"Watering: {advice['watering']}\n"
                        f"Spray: {advice['spray']}\n"
                        f"Extra: {advice.get('extra', 'None')}\n"
                        f"Confidence: {advice.get('confidence', 'None')}\n"
                        f"{mandi_summary}"
                    ),
                },
            ],
            max_tokens=300,
            temperature=0.2,
        )

        return response.choices[0].message.content

    except Exception as e:
        print(f"Error generating briefing for {farmer_id}: {e}")
        return None


async def process_farmer(farmer):
    async for db in get_db():
        try:
            briefing = await generate_briefing(db, farmer.phone_number)

            if briefing:
                await send_whatsapp(farmer.phone_number, briefing)
                print(f"Briefing sent for {farmer.phone_number}")
            else:
                print(f"No briefing for {farmer.phone_number}")
            print(f"Farmer processed: {farmer.phone_number}")
            return
        except Exception as e:
            print(f"Failed for {farmer.phone_number}: {e}")
            return


async def send_morning_briefings():
    print(f"\nStarting briefings - {datetime.now()}")

    async for db in get_db():
        result = await db.execute(select(Farmer))
        farmers = result.scalars().all()
        break

    if not farmers:
        print("No farmers found")
        return

    print(f"Total farmers: {len(farmers)}")

    tasks = []
    for farmer in farmers:
        tasks.append(process_farmer(farmer))
        await asyncio.sleep(0.2)

    await asyncio.gather(*tasks)

    print("All briefings sent\n")


scheduler = AsyncIOScheduler()


def start_scheduler():
    scheduler.add_job(
        send_morning_briefings,
        CronTrigger(hour=8, minute=0, timezone="Asia/Kolkata"),
        id="morning_briefing",
        replace_existing=True,
    )

    scheduler.start()
    print("Scheduler started (8:00 AM IST)")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        print("Scheduler stopped")
