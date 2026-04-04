"""
Guardrails for incoming WhatsApp messages and media.
"""

import re
from dataclasses import dataclass


@dataclass
class GuardrailResult:
    allowed: bool
    reply: str = ""
    warning: str = ""


BLOCKED_PATTERNS = [
    (r"\b(suicide|khud ko maarna|zindagi khatam|mar jaana chahta)\b", "mental_health"),
    (r"\b(pesticide peena|zeher peena|poison pee|zeher khaana)\b", "self_harm"),
]

OUT_OF_SCOPE = [
    "cricket",
    "ipl",
    "bollywood",
    "movie",
    "film",
    "politics",
    "election",
    "vote",
    "share market",
    "sensex",
    "nifty",
    "stock",
]

FARMING_KEYWORDS = [
    "crop", "plant", "leaf", "soil", "disease", "spray", "mandi",
    "price", "rain", "fertilizer", "pest", "harvest", "seed", "farm",
    "field", "khet", "irrigation", "yield", "sowing",
    "fasal", "paudha", "patta", "mitti", "bimari", "khad", "kida",
    "katai", "beej", "bhav", "barish", "gehu", "chawal", "pyaz",
    "tamatar", "aloo", "kapas", "ganna", "arhar", "moong", "bajra",
    "tomato", "onion", "wheat", "rice", "potato", "cotton",
    "sugarcane", "maize", "soybean", "mustard", "groundnut",
    "brinjal", "cabbage", "cauliflower", "chilli", "garlic", "ginger",
]


def check_message(message: str) -> GuardrailResult:
    msg_lower = (message or "").lower()

    for pattern, category in BLOCKED_PATTERNS:
        if re.search(pattern, msg_lower):
            return GuardrailResult(
                allowed=False,
                reply=(
                    "Bhai, lagta hai aap mushkil waqt se guzar rahe hain. "
                    "Kripya Vandrevala Foundation helpline 1860-2662-345 par call karein "
                    "(24x7, free). Aap akele nahi hain."
                ),
                warning=f"BLOCKED: {category}",
            )

    if any(kw in msg_lower for kw in FARMING_KEYWORDS):
        return GuardrailResult(allowed=True)

    for kw in OUT_OF_SCOPE:
        if kw in msg_lower:
            return GuardrailResult(
                allowed=False,
                reply=(
                    "Bhai, main sirf kheti mein help kar sakta hoon.\n"
                    "Fasal, mandi price, ya paudhe ki bimari ke baare mein poochho."
                ),
                warning=f"OUT_OF_SCOPE: {kw}",
            )

    return GuardrailResult(allowed=True)


def check_image(content_type: str) -> GuardrailResult:
    allowed = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
    if content_type and content_type.lower() in allowed:
        return GuardrailResult(allowed=True)
    return GuardrailResult(
        allowed=False,
        reply=(
            "Bhai, sirf photo bhejo (JPG/PNG/WEBP).\n"
            "Voice note aur video abhi support nahi hai."
        ),
        warning=f"UNSUPPORTED_MEDIA: {content_type}",
    )
