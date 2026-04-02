"""
scheduler.py  (agent/)
Base: agent/scheduler.py
Merged in: weather fetching, farming condition analysis,
           LLM-powered briefing from services/scheduler.py
"""

import asyncio
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Any

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
from sqlalchemy import select

from backend.agent.agent import client as groq_client
from backend.agent.tools import get_mandi_price_from_db, get_treatment
from backend.db.crud import get_farmer_profile
from backend.db.deps import get_db
from backend.db.models import Farmer
from scripts.scrape_karnataka_napanta import run as run_karnataka_scraper
from services.whatsapp_service import send_proactive_message

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
OPENWEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"

DEFAULT_WEATHER: dict[str, float] = {
    "temp": 30.0,
    "humidity": 50.0,
    "rain": 0.0,
    "wind": 5.0,
}
WEATHER_CACHE_TTL = 1800
weather_cache: dict[str, tuple[dict[str, float], float]] = {}
http_client = httpx.AsyncClient(timeout=10.0)

scheduler = AsyncIOScheduler()
_executor = ThreadPoolExecutor(max_workers=1)


# ── Weather helpers ───────────────────────────────────────────────────────────


def _safe_float(value: Any, fallback: float) -> float:
    try:
        return float(value) if value is not None else fallback
    except (TypeError, ValueError):
        return fallback


def _extract_metric(pattern: str, text: str, fallback: float) -> float:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return _safe_float(match.group(1), fallback) if match else fallback


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
    text = str(weather_result or "")
    return {
        "temp": _extract_metric(
            r"temperature\s*[:=]\s*(-?\d+(?:\.\d+)?)", text, DEFAULT_WEATHER["temp"]
        ),
        "humidity": _extract_metric(
            r"humidity\s*[:=]\s*(\d+(?:\.\d+)?)", text, DEFAULT_WEATHER["humidity"]
        ),
        "rain": _extract_metric(
            r"(?:rain|precipitation)(?:\s+chance)?\s*[:=]\s*(\d+(?:\.\d+)?)",
            text,
            DEFAULT_WEATHER["rain"],
        ),
        "wind": _extract_metric(
            r"wind(?:\s+speed)?\s*[:=]\s*(\d+(?:\.\d+)?)", text, DEFAULT_WEATHER["wind"]
        ),
    }


async def fetch_weather_api(location: str) -> dict[str, float]:
    print(f"[Scheduler] Fetching weather: {location}")
    key = location.strip().lower()
    cached = weather_cache.get(key)
    if cached and time.time() - cached[1] < WEATHER_CACHE_TTL:
        return cached[0]

    if not OPENWEATHER_API_KEY:
        return normalize_weather_data(DEFAULT_WEATHER)

    for attempt in range(2):
        try:
            response = await http_client.get(
                OPENWEATHER_URL,
                params={"q": location, "appid": OPENWEATHER_API_KEY, "units": "metric"},
            )
            response.raise_for_status()
            p = response.json()
            parsed = normalize_weather_data(
                {
                    "temp": p.get("main", {}).get("temp"),
                    "humidity": p.get("main", {}).get("humidity"),
                    "rain": p.get("rain", {}).get("1h", 0.0),
                    "wind": p.get("wind", {}).get("speed"),
                }
            )
            if len(weather_cache) > 100:
                weather_cache.clear()
            weather_cache[key] = (parsed, time.time())
            return parsed
        except Exception as e:
            print(
                f"[Scheduler] Weather fetch attempt {attempt + 1} failed ({location}): {e}"
            )
            if attempt == 1:
                return normalize_weather_data(DEFAULT_WEATHER)


async def close_http_client():
    await http_client.aclose()


# ── Farming condition analysis ────────────────────────────────────────────────


def analyze_farming_conditions(
    weather: dict[str, Any],
    disease: str | None,
    crops: list[str] | None,
) -> dict[str, str]:
    humidity = _safe_float(weather.get("humidity"), DEFAULT_WEATHER["humidity"])
    rain = _safe_float(weather.get("rain"), DEFAULT_WEATHER["rain"])
    wind = _safe_float(weather.get("wind"), DEFAULT_WEATHER["wind"])
    hour = datetime.now().hour
    crop_names = [str(c).strip().lower() for c in (crops or []) if c]

    advice: dict[str, str] = {
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


# ── LLM briefing generation ───────────────────────────────────────────────────


async def generate_briefing(db, farmer_id: str) -> str | None:
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
            print(f"[Scheduler] Skipping {farmer_id} — no location")
            return None

        weather_data = await fetch_weather_api(location)
        advice = analyze_farming_conditions(weather_data, recent_disease, crops)

        mandi_summary = ""
        if crops:
            try:
                price = await get_mandi_price_from_db(db, crops[0], location)
                mandi_summary = f"\nMandi price ({crops[0]}): {price}"[:200]
            except Exception as e:
                print(f"[Scheduler] Mandi price failed for {farmer_id}: {e}")

        today = datetime.now().strftime("%A, %d %B %Y")
        spray_line = (
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
                        "Include:\n"
                        "1. Weather summary\n"
                        "2. Watering advice\n"
                        f"{spray_line}\n"
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
                        f"Temp: {weather_data['temp']}\u00b0C | "
                        f"Humidity: {weather_data['humidity']}% | "
                        f"Rain: {weather_data['rain']} mm | "
                        f"Wind: {weather_data['wind']} km/h\n\n"
                        f"Watering: {advice['watering']}\n"
                        f"Spray: {advice['spray']}\n"
                        f"Extra: {advice.get('extra', 'None')}\n"
                        f"{mandi_summary}"
                    ),
                },
            ],
            max_tokens=300,
            temperature=0.2,
        )
        return response.choices[0].message.content

    except Exception as e:
        print(f"[Scheduler] generate_briefing error for {farmer_id}: {e}")
        return None


# ── Per-farmer task ───────────────────────────────────────────────────────────


async def process_farmer(farmer):
    async for db in get_db():
        try:
            briefing = await generate_briefing(db, farmer.phone_number)
            if briefing:
                await send_proactive_message(farmer.phone_number, briefing)
                print(f"[Scheduler] Sent briefing → {farmer.phone_number}")
            else:
                print(f"[Scheduler] No briefing for {farmer.phone_number}")
        except Exception as e:
            print(f"[Scheduler] Failed for {farmer.phone_number}: {e}")
        return


# ── Scheduled jobs ────────────────────────────────────────────────────────────


async def send_morning_briefings():
    print(f"\n[Scheduler] Morning briefings starting — {datetime.now()}")
    async for db in get_db():
        result = await db.execute(select(Farmer))
        farmers = result.scalars().all()
        break

    if not farmers:
        print("[Scheduler] No farmers found")
        return

    print(f"[Scheduler] {len(farmers)} farmers to brief")
    tasks = [process_farmer(f) for f in farmers]
    for t in tasks:
        await asyncio.sleep(0.2)
    await asyncio.gather(*tasks)
    print("[Scheduler] All briefings done\n")


async def daily_karnataka_scrape():
    print(f"[Scheduler] Karnataka scrape starting — {datetime.now()}")
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(_executor, run_karnataka_scraper)
        print("[Scheduler] Karnataka scrape done")
    except Exception as e:
        print(f"[Scheduler] Karnataka scrape failed: {e}")


# ── Follow-up scheduling ──────────────────────────────────────────────────────


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
    print(f"[Scheduler] Follow-up for {phone} on {followup_date.date()}")


async def _send_followup(
    phone: str, farmer_name: str, disease_name: str, bbox_pct: float
):
    msg = (
        f"{farmer_name} bhai, 3 din pehle aapki fasal mein "
        f"{disease_name} thi ({bbox_pct}% affected).\n"
        f"Kya dawai laga di? Aur ab kaisa lag raha hai?\n"
        f"Ek nayi photo bhejein — main dekh leta hoon. \U0001f4f8"
    )
    await send_proactive_message(phone, msg)
    print(f"[Scheduler] Follow-up sent → {phone}")


# ── Lifecycle ─────────────────────────────────────────────────────────────────


def start_scheduler():
    scheduler.add_job(
        send_morning_briefings,
        CronTrigger(hour=8, minute=0, timezone="Asia/Kolkata"),
        id="morning_briefing",
        replace_existing=True,
    )
    scheduler.add_job(
        daily_karnataka_scrape,
        CronTrigger(hour=8, minute=20, timezone="Asia/Kolkata"),
        id="daily_karnataka_scrape",
        replace_existing=True,
    )
    scheduler.start()
    print("[Scheduler] Started. Jobs:")
    for job in scheduler.get_jobs():
        print(f"  {job.id} → {job.next_run_time}")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        print("[Scheduler] Stopped")
