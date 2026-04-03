from outbreak.db_queries import get_nearby_farmers, distance_km, get_direction
import services.whatsapp_service as ws
from groq import AsyncGroq

groq_client = AsyncGroq()  # uses GROQ_API_KEY from env

async def get_preventive_steps_ai(disease, crop):
    response = await groq_client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[{
            "role": "user",
            "content": f"Give exactly 4 short preventive steps for {disease} in {crop} crops. Return only a numbered list, no extra text."
        }],
        max_tokens=150
    )
    text = response.choices[0].message.content.strip()
    steps = [line.lstrip("1234567890.). ").strip() for line in text.split("\n") if line.strip()]
    return steps[:4]


def get_preventive_steps(disease):
    disease = disease.lower()
    if "blight" in disease:
        return ["Avoid overhead irrigation", "Remove infected leaves immediately", "Use copper-based fungicide", "Ensure proper spacing between plants"]
    if "rust" in disease:
        return ["Spray fungicide early", "Avoid excess nitrogen fertilizer", "Monitor leaves daily"]
    return None  # fallback to Groq


async def build_message(farmer, detection, is_same_crop):
    dist = round(distance_km(farmer["lat"], farmer["lng"], detection["lat"], detection["lng"]), 2)
    direction = get_direction(farmer["lat"], farmer["lng"], detection["lat"], detection["lng"])

    steps = get_preventive_steps(detection["disease_name"])
    if steps is None:
        steps = await get_preventive_steps_ai(detection["disease_name"], detection["crop_type"])

    steps_text = "\n".join([f"• {s}" for s in steps])

    header = f"🔥 Outbreak detected: {detection['disease_name']}\n📲 ALERT FOR FARMER: {farmer['phone']}\n" if is_same_crop else ""

    return f"""{header}
⚠️ Nearby farm has {detection['disease_name']}
📍 The outbreak is {dist} km away
🧭 Direction: {direction}

Even if you grow different crops,
monitor your farm for early signs.

🌱 Preventive Steps:
{steps_text}

Stay alert 🚜"""


async def handle_new_detection(db, detection):
    if detection["severity"] != 5 or not detection["spread"]:
        return {"status": "no_alert_needed"}

    nearby_farmers = get_nearby_farmers(db, detection["lat"], detection["lng"], radius_km=50)
    nearby_farmers = [f for f in nearby_farmers if f["phone"] != detection["phone"]]

    target_farmers = [f for f in nearby_farmers if detection["crop_type"] in (f["crops"] or [])]
    other_farmers = [f for f in nearby_farmers if detection["crop_type"] not in (f["crops"] or [])]

    for farmer in target_farmers:
        msg = await build_message(farmer, detection, is_same_crop=True)
        await ws.send_proactive_message(farmer["phone"], msg)

    for farmer in other_farmers:
        msg = await build_message(farmer, detection, is_same_crop=False)
        await ws.send_proactive_message(farmer["phone"], msg)

    return {"alerts_sent": len(target_farmers), "cross_alerts_sent": len(other_farmers)}