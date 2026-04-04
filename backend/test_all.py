import asyncio

from backend.services.whatsapp_service import handle_incoming_message
from backend.scheduler import _send_followup, check_price_alerts
from backend.outbreak.service import handle_new_detection


PHONE = "whatsapp:+911234567890"


# -------------------------------
# Helper to simulate message
# -------------------------------
async def send(body="", lat=None, lng=None):
    form_data = {
        "From": PHONE,
        "Body": body,
        "NumMedia": "0",
        "Latitude": lat,
        "Longitude": lng,
    }

    res = await handle_incoming_message(form_data)
    if res:
        print("\n🤖 RESPONSE:\n", res)
    print("\n" + "=" * 60)


# -------------------------------
# FULL FLOW TEST
# -------------------------------
async def run_all_tests():
    print("\n🚀 STARTING FULL SYSTEM TEST\n")

    # 1️⃣ Language selection
    print("\n🔹 TEST 1: LANGUAGE")
    await send("Hi")
    await send("1")

    # 2️⃣ Save location
    print("\n🔹 TEST 2: LOCATION SAVE")
    await send("", lat="12.97", lng="77.59")

    # 3️⃣ Mandi without crop
    print("\n🔹 TEST 3: MANDI WITHOUT CROP")
    await send("nearby mandis")

    # 4️⃣ Mandi with crop
    print("\n🔹 TEST 4: MANDI WITH CROP")
    await send("tomato price")

    # 5️⃣ Text location override
    print("\n🔹 TEST 5: LOCATION OVERRIDE")
    await send("tomato price in salem")

    # 6️⃣ Treatment without disease
    print("\n🔹 TEST 6: TREATMENT WITHOUT DISEASE")
    await send("treatment")

    # 7️⃣ Simulate disease detection manually
    print("\n🔹 TEST 7: SIMULATED DISEASE DETECTION")
    detection = {
        "phone": "+911234567890",
        "disease_name": "Late Blight",
        "crop_type": "tomato",
        "severity": 8,
        "lat": 12.97,
        "lng": 77.59,
        "spread": True,
    }

    await handle_new_detection(None, detection)

    # 8️⃣ Treatment after disease
    print("\n🔹 TEST 8: TREATMENT AFTER DISEASE")
    await send("treatment")

    # 9️⃣ Follow-up direct trigger
    print("\n🔹 TEST 9: FOLLOW-UP")
    await _send_followup(
        phone="+911234567890",
        farmer_name="Test Farmer",
        disease_name="Late Blight",
        bbox_pct=40,
    )

    # 🔟 Price alert check
    print("\n🔹 TEST 10: PRICE ALERT")
    await check_price_alerts()

    print("\n✅ ALL TESTS COMPLETED\n")


# -------------------------------
# RUN
# -------------------------------
if __name__ == "__main__":
    asyncio.run(run_all_tests())