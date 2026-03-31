import os
from twilio.rest import Client

def _get_twilio_client():
    sid   = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    if not sid or not token:
        raise EnvironmentError("TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN must be set in .env")
    return Client(sid, token)

TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")

def _severity_emoji(level):
    return {"Mild": "🟡", "Moderate": "🟠", "Severe": "🔴"}.get(level, "⚪")

def format_single_diagnosis(diagnosis, index=1, total=1):
    sev   = diagnosis.get("severity", {})
    level = sev.get("level", "Unknown")
    emoji = _severity_emoji(level)
    lines = []

    if total > 1:
        lines += [f"*Detection {index} of {total}*", ""]

    lines += [
        f"🔍 *Disease:* {diagnosis.get('display_name', 'Unknown')}",
        f"🌱 *Crop:* {diagnosis.get('crop', 'Unknown')}",
        f"🦠 *Cause:* {diagnosis.get('pathogen', 'Unknown')}",
        f"{emoji} *Severity:* {level} ({sev.get('bbox_pct', 0):.1f}% of leaf affected)",
        f"🎯 *Confidence:* {sev.get('confidence_pct', 0):.1f}%",
        "",
    ]

    if diagnosis.get("symptoms"):
        lines += ["📋 *Symptoms:*", diagnosis["symptoms"], ""]

    chemical = diagnosis.get("remedies", {}).get("chemical", [])
    if chemical:
        lines.append("💊 *Treatment (Chemical):*")
        lines += [f"  • {r}" for r in chemical[:3]]
        lines.append("")

    organic = diagnosis.get("remedies", {}).get("organic", [])
    if organic:
        lines.append("🌿 *Organic Options:*")
        lines += [f"  • {r}" for r in organic[:3]]
        lines.append("")

    prevention = diagnosis.get("remedies", {}).get("prevention", [])
    if prevention:
        lines.append("🛡️ *Prevention:*")
        lines += [f"  • {r}" for r in prevention[:2]]
        lines.append("")

    if diagnosis.get("urgency"):
        lines.append(f"⚠️ *Action:* {diagnosis['urgency']}")

    if diagnosis.get("regional_note"):
        lines += ["", f"📍 *Local Note:* {diagnosis['regional_note']}"]

    return "\n".join(lines)

def format_diagnosis_message(result):
    status = result.get("status")
    header = "🌾 *KrishiMitra — Crop Diagnosis*\n" + "─" * 30 + "\n\n"

    if status == "healthy":
        return (header + "✅ *Your crop looks healthy!*\n\n"
                "No disease detected.\n\n"
                "💡 *Tips to keep it healthy:*\n"
                "  • Scout your field every 3-4 days\n"
                "  • Remove any yellowing leaves promptly\n"
                "  • Water at soil level, not on leaves\n\n"
                "_KrishiMitra is watching over your crops_ 🌱")

    if status == "no_detection":
        return (header + "🔍 *Could not identify a disease clearly.*\n\n"
                "Tips for a better photo:\n"
                "  • Hold phone 15-20cm from the leaf\n"
                "  • Use natural daylight, avoid flash\n"
                "  • Capture the entire affected leaf\n"
                "  • Keep the image in focus\n\n"
                "Please send another photo and we will try again.")

    diagnoses = result.get("diagnoses", [])
    total     = len(diagnoses)
    overall   = result.get("overall_severity", "")
    parts     = [header]

    if total > 1:
        parts.append(f"⚡ *{total} issues detected* — Overall: {_severity_emoji(overall)} {overall}\n\n")

    for i, d in enumerate(diagnoses, 1):
        parts.append(format_single_diagnosis(d, index=i, total=total))
        if i < total:
            parts.append("\n" + "─" * 20 + "\n\n")

    parts.append("\n\n_Reply with another photo or ask any farming question_ 🌾")
    return "\n".join(parts)

def send_diagnosis(to, result):
    body    = format_diagnosis_message(result)
    to_wa   = f"whatsapp:{to}" if not to.startswith("whatsapp:") else to
    client  = _get_twilio_client()
    msg     = client.messages.create(body=body, from_=TWILIO_WHATSAPP_NUMBER, to=to_wa)
    return msg.sid

def parse_incoming_whatsapp(form_data):
    return {
        "from":       form_data.get("From", "").replace("whatsapp:", ""),
        "body":       form_data.get("Body", "").strip(),
        "media_url":  form_data.get("MediaUrl0"),
        "media_type": form_data.get("MediaContentType0"),
    }