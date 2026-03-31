import os
import asyncio
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
from twilio.rest import Client

from sqlalchemy import select

# Load env
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Tools
from agent.tools import get_weather, get_mandi_price, get_treatment
from agent.agent import client as groq_client

# DB
from backend.db.deps import get_db
from backend.db.models import Farmer
from backend.db.crud import get_farmer_profile


# ─────────────────────────────────────────────────────────
# 📲 WhatsApp Sender (with retry)
# ─────────────────────────────────────────────────────────
def send_whatsapp(to: str, message: str, retries=3):
    for attempt in range(retries):
        try:
            client = Client(
                os.getenv("TWILIO_ACCOUNT_SID"),
                os.getenv("TWILIO_AUTH_TOKEN"),
            )

            client.messages.create(
                from_=os.getenv("TWILIO_WHATSAPP_NUMBER"),
                to=to,
                body=message,
            )

            print(f"✅ Sent to {to}")
            return

        except Exception as e:
            print(f"⚠️ Retry {attempt + 1} failed for {to}: {e}")
            asyncio.sleep(2)

    print(f"❌ Failed to send to {to} after retries")


# ─────────────────────────────────────────────────────────
# 🧠 Generate Briefing (DB-based)
# ─────────────────────────────────────────────────────────
async def generate_briefing(db, farmer_id: str) -> str:
    try:
        profile = await get_farmer_profile(db, farmer_id)

        farmer = profile["farmer"]
        crops = profile["crops"]
        recent_disease = profile["recent_disease"]

        if not farmer:
            return None

        location = farmer.location or "Bangalore"
        language = farmer.language or "Hindi"

        print(f"\n📍 Farmer: {farmer_id}")
        print(f"   Location: {location}")
        print(f"   Crops: {crops}")
        print(f"   Disease: {recent_disease}")

        # ─── Tool Calls ─────────────────────────
        tool_data = []

        weather = get_weather.run(location)
        tool_data.append(f"Weather:\n{weather}")

        for crop in crops[:2]:
            price = get_mandi_price.run(crop)
            tool_data.append(f"Price for {crop}:\n{price}")

        if recent_disease:
            treatment = get_treatment.run(recent_disease)
            tool_data.append(f"Disease follow-up:\n{treatment}")

        # ─── Generate Message ───────────────────
        today = datetime.now().strftime("%A, %d %B %Y")

        response = await groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": f"""You are KrishiMitra.

Today is {today}, 8:00 AM.

Rules:
- Reply in {language}
- Max 5 bullet points
- Start with morning greeting
- Include weather risk
- Include mandi prices
- Include disease follow-up if exists
- End with ONE clear action
- Friendly tone""",
                },
                {
                    "role": "user",
                    "content": (
                        f"Location: {location}\n"
                        f"Crops: {', '.join(crops)}\n"
                        f"Disease: {recent_disease or 'None'}\n\n"
                        f"Data:\n{chr(10).join(tool_data)}"
                    ),
                },
            ],
            max_tokens=300,
            temperature=0.4,
        )

        return response.choices[0].message.content

    except Exception as e:
        print(f"❌ Error generating briefing for {farmer_id}: {e}")
        return None


# ─────────────────────────────────────────────────────────
# 🚀 Process Single Farmer
# ─────────────────────────────────────────────────────────
async def process_farmer(db, farmer):
    try:
        briefing = await generate_briefing(db, farmer.phone_number)

        if briefing:
            send_whatsapp(farmer.phone_number, briefing)
        else:
            print(f"⚠️ No briefing for {farmer.phone_number}")

    except Exception as e:
        print(f"❌ Failed for {farmer.phone_number}: {e}")


# ─────────────────────────────────────────────────────────
# 🌅 Main Scheduler Job
# ─────────────────────────────────────────────────────────
async def send_morning_briefings():
    print(f"\n🌅 Starting briefings — {datetime.now()}")

    async for db in get_db():
        result = await db.execute(select(Farmer))
        farmers = result.scalars().all()

        if not farmers:
            print("⚠️ No farmers found")
            return

        print(f"👨‍🌾 Total farmers: {len(farmers)}")

        # 🔥 Parallel execution
        tasks = [process_farmer(db, farmer) for farmer in farmers]
        await asyncio.gather(*tasks)

    print("✅ All briefings sent\n")


# ─────────────────────────────────────────────────────────
# ⏰ Scheduler Setup
# ─────────────────────────────────────────────────────────
scheduler = AsyncIOScheduler()


def start_scheduler():
    scheduler.add_job(
        send_morning_briefings,
        CronTrigger(hour=8, minute=0, timezone="Asia/Kolkata"),
        id="morning_briefing",
        replace_existing=True,
    )

    scheduler.start()
    print("✅ Scheduler started (8:00 AM IST)")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        print("🛑 Scheduler stopped")
