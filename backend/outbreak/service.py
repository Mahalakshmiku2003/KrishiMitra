from outbreak.db_queries import get_nearby_farmers
from services.whatsapp_service import send_proactive_message
from sqlalchemy import text

async def handle_new_detection(db, detection):

    if detection["severity"] != 5 or not detection["spread"]:
        return {"status": "no_alert_needed"}

    nearby_farmers = get_nearby_farmers(
        db,
        detection["lat"],
        detection["lng"],
        radius_km=50
    )

    # ✅ SAME CROP ALERTS
    target_farmers = [
        f for f in nearby_farmers
        if detection["crop_type"] in (f["crops"] or [])
    ]

    for farmer in target_farmers:
        await send_alert(farmer, detection)

    # ✅ CROSS-CROP ALERTS (FIXED ✅)
    other_farmers = [
        f for f in nearby_farmers
        if detection["crop_type"] not in (f["crops"] or [])
    ]

    for farmer in other_farmers:
        await send_cross_crop_alert(farmer, detection)

    return {
        "alerts_sent": len(target_farmers),
        "cross_alerts_sent": len(other_farmers)
    }


async def send_alert(farmer, detection):
    print(f"📤 Sending alert to {farmer['phone']}")

    message = f"""
🚨 URGENT FARM ALERT

Disease: {detection['disease_name']}
Severity: HIGH

Check your {detection['crop_type']} crop immediately.
"""

    await send_proactive_message(farmer["phone"], message)


async def send_cross_crop_alert(farmer, detection):
    print(f"⚠️ Cross alert to {farmer['phone']}")

    message = f"""
⚠️ Nearby farm has {detection['disease_name']}

Even if you grow different crops,
monitor your farm for early signs.
"""

    await send_proactive_message(farmer["phone"], message)