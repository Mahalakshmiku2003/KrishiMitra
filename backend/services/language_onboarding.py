"""
First-contact language selection for WhatsApp. Persists to farmers.language via farmer_store.
"""

from __future__ import annotations

import re

from farmer_store import get_farmer_language, set_farmer_language, normalize_phone
from services.profile_state import mark_pending_name

LANGUAGE_PROMPT = """🌾 KrishiMitra mein aapka swagat hai!
ಕೃಷಿಮಿತ್ರಕ್ಕೆ ಸ್ವಾಗತ! / Welcome to KrishiMitra!

Apni bhasha chunein:
ನಿಮ್ಮ ಭಾಷೆ ಆಯ್ಕೆ ಮಾಡಿ:
Choose your language:

1️⃣  हिंदी (Hindi)
2️⃣  ಕನ್ನಡ (Kannada)
3️⃣  English

1, 2 ya 3 reply karein / 1, 2 ಅಥವಾ 3 ಉತ್ತರಿಸಿ / Reply with 1, 2 or 3"""

_CONFIRM = {
    "hindi": (
        "Dhanyavaad! Aapki bhasha *Hindi* set ho gayi hai.\n\n"
        "Ab kripya apna *naam* type karke bhejein (ek line mein).\n\n"
        "Koi aur madad chahiye? 🌾"
    ),
    "kannada": (
        "ಧನ್ಯವಾದಗಳು! ನಿಮ್ಮ ಭಾಷೆ *ಕನ್ನಡ* ಆಯ್ಕೆ ಮಾಡಲಾಗಿದೆ.\n\n"
        "ಈಗ ದಯವಿಟ್ಟು ನಿಮ್ಮ *ಹೆಸರು* ಟೈಪ್ ಮಾಡಿ (ಒಂದೇ ಸಾಲು).\n\n"
        "ಮತ್ತಷ್ಟು ಸಹಾಯ ಬೇಕೇ? 🌾"
    ),
    "english": (
        "Thank you! Your language is set to *English*.\n\n"
        "Please type your *name* (one line).\n\n"
        "Need anything else? 🌾"
    ),
}


def _is_simple_greeting(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    words = t.split()
    if len(words) > 3:
        return False
    greetings = frozenset(
        {
            "hi",
            "hello",
            "hey",
            "namaste",
            "namaskar",
            "hlo",
            "hii",
            "hallo",
            "helo",
        }
    )
    if t in greetings:
        return True
    if len(words) == 2 and words[0] == "good" and words[1] in (
        "morning",
        "evening",
        "afternoon",
        "night",
    ):
        return True
    return False


def _parse_language_choice(text: str) -> str | None:
    t = (text or "").strip()
    if not t:
        return None
    digit_only = "".join(c for c in t if c.isdigit())
    if len(digit_only) != 1 or digit_only not in "123":
        return None
    # Avoid "1 tomato" / "option 2 please" — require no letter scripts in the message
    if re.search(r"[a-zA-Z\u0900-\u0FFF\u0C80-\u0CFF]", t):
        return None
    return {"1": "hindi", "2": "kannada", "3": "english"}[digit_only]


def maybe_handle_language_onboarding(phone: str, body: str) -> str | None:
    """
    If farmer has no language set:
    - greeting -> return language menu
    - 1 / 2 / 3 -> save language and return confirmation
    Otherwise return None (caller continues normal flow).
    """
    pid = normalize_phone(phone)
    if get_farmer_language(pid):
        return None

    choice = _parse_language_choice(body)
    if choice:
        set_farmer_language(pid, choice)
        mark_pending_name(pid)
        return _CONFIRM[choice]

    if _is_simple_greeting(body):
        return LANGUAGE_PROMPT

    return None
 