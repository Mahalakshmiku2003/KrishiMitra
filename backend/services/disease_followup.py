"""Periodic WhatsApp follow-ups for recent disease diagnoses (every 2 days, max 5)."""

from __future__ import annotations

from farmer_store import (
    bump_disease_followup_schedule,
    get_farmer_location,
    iter_disease_followups_due,
    normalize_phone,
)
from services.medicine_links import remedy_buy_links
from services.whatsapp_service import handle_location_for_mandi, send_proactive_message


def _commodity_from_snap(snap: dict) -> str:
    crop = snap.get("crop_stated") or snap.get("crop_model") or ""
    low = str(crop).lower()
    for c in [
        "tomato",
        "potato",
        "onion",
        "wheat",
        "rice",
        "cotton",
        "corn",
        "grape",
        "pepper",
        "mango",
        "banana",
    ]:
        if c in low:
            return c
    return "tomato"


def _mild_line(snap: dict) -> str:
    rem = snap.get("remedies") or {}
    for key in ("organic", "chemical"):
        for line in rem.get(key, [])[:1]:
            t = (line or "").strip()
            if len(t) > 5:
                return t
    return "Continue light preventive care as per local adviser's guidance."


async def send_due_disease_followups() -> None:
    due = iter_disease_followups_due()
    if not due:
        return

    for row in due:
        phone = row["phone"]
        name = row["farmer_name"]
        lang = (row.get("farmer_language") or "").strip().lower()
        snap = row["snap"]
        disease = snap.get("disease") or "crop issue"
        mild = _mild_line(snap)
        commodity = _commodity_from_snap(snap)
        rem = snap.get("remedies") or {}
        links = remedy_buy_links(rem)
        link_txt = "\n".join(f"• {u}" for u in links) if links else ""

        mandi_block = ""
        loc = get_farmer_location(normalize_phone(phone))
        if loc:
            try:
                mandi_block = await handle_location_for_mandi(
                    phone,
                    loc["lat"],
                    loc["lng"],
                    commodity,
                    state_filter=None,
                )
            except Exception as e:
                print(f"[Followup] Mandi block failed for {phone}: {e}")

        if lang == "kannada":
            msg = (
                f"ನಮಸ್ಕಾರ {name},\n"
                f"ಹಿಂದಿನ ರೋಗ ತಪಾಸಣೆ ({disease}) — ಈಗ ಫಸಲು ಹೇಗಿದೆ?\n"
                f"ಸಾಧ್ಯವಾದರೆ ಹೊಸ ಫೋಟೋ ಕಳುಹಿಸಿ.\n\n"
                f"ಸೌಮ್ಯ ನಿರ್ವಹಣೆ: {mild}\n"
            )
        elif lang == "english":
            msg = (
                f"Hello {name},\n"
                f"Follow-up on your crop issue ({disease}). How is the crop now?\n"
                f"Please send a fresh photo if you can.\n\n"
                f"Milder care: {mild}\n"
            )
        else:
            msg = (
                f"Namaste {name},\n"
                f"Pehle wali beemari ({disease}) ke baad ab fasal kaisi hai?\n"
                f"Ho sake to nayi photo bhejein.\n\n"
                f"Halki dekhbhaal: {mild}\n"
            )

        if mandi_block:
            msg += f"\n{mandi_block}\n"
        if link_txt:
            msg += f"\n*Dawai / input khareedne ke links (online search):*\n{link_txt}\n"
        msg += "\nKoi aur madad chahiye? 🌾"

        await send_proactive_message(phone, msg)
        bump_disease_followup_schedule(phone)
        print(f"[Followup] Sent disease follow-up to {phone}")
