"""
After language is chosen, collect farmer name once and save to farmers.name.
"""

from __future__ import annotations

import re

from farmer_store import get_farmer_language, normalize_phone, update_farmer_profile
from services.profile_state import clear_pending_name, is_pending_name

_NAME_TOO_LONG = 80


def _name_prompt(lang: str | None) -> str:
    if lang == "kannada":
        return (
            "ದಯವಿಟ್ಟು ನಿಮ್ಮ *ಹೆಸರು* ಟೈಪ್ ಮಾಡಿ (ಒಂದೇ ಸಾಲು):\n\n"
            "Koi aur madad chahiye? 🌾"
        )
    if lang == "english":
        return (
            "Please type your *name* (one line):\n\n"
            "Need anything else? 🌾"
        )
    return (
        "Kripya apna *naam* type karke bhejein (ek line mein):\n\n"
        "Koi aur madad chahiye? 🌾"
    )


def _name_thanks(lang: str | None, name: str) -> str:
    if lang == "kannada":
        return f"ಧನ್ಯವಾದಗಳು, *{name}*! ನಿಮ್ಮನ್ನು ಭೇಟಿಯಾಗಿ ಸಂತೋಷವಾಯಿತು. 🌾\n\nಮುಂದಿನ ಸಹಾಯಕ್ಕೆ ಸಂದೇಶ ಕಳುಹಿಸಿ."
    if lang == "english":
        return f"Thank you, *{name}*! Nice to meet you. 🌾\n\nSend a message anytime you need help."
    return (
        f"Dhanyavaad, *{name}* bhai! Aapse milkar accha laga. 🌾\n\n"
        f"Madad ke liye kabhi bhi message bhejein."
    )


def _invalid_name_reply(lang: str | None) -> str:
    if lang == "kannada":
        return "ದಯವಿಟ್ಟು ನಿಜವಾದ ಹೆಸರು ಟೈಪ್ ಮಾಡಿ (ಅಂಕೆಗಳು ಮಾತ್ರ ಅಲ್ಲ).\n\nKoi aur madad chahiye? 🌾"
    if lang == "english":
        return "Please type a real name (not only numbers).\n\nNeed anything else? 🌾"
    return "Kripya sahi naam likhein (sirf number nahi).\n\nKoi aur madad chahiye? 🌾"


def maybe_handle_name_onboarding(phone: str, body: str) -> str | None:
    """
    If waiting for name after language selection, save trimmed text as farmers.name.
    Returns reply TwiML body if handled, else None.
    """
    pid = normalize_phone(phone)
    if not is_pending_name(pid):
        return None

    lang = get_farmer_language(pid)
    raw = (body or "").strip()
    if not raw:
        return _name_prompt(lang)

    if len(raw) > _NAME_TOO_LONG:
        return _invalid_name_reply(lang)

    # At least one letter (Latin / Devanagari / Kannada scripts)
    if not re.search(
        r"[a-zA-Z\u0900-\u0FFF\u0C80-\u0CFF]", raw, re.UNICODE
    ):
        return _invalid_name_reply(lang)

    clean = re.sub(r"\s+", " ", raw).strip()
    update_farmer_profile(pid, name=clean)
    clear_pending_name(pid)
    return _name_thanks(lang, clean)
