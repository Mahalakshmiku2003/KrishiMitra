"""
After language is chosen, collect farmer display name once.
"""

from __future__ import annotations

from farmer_store import (
    get_farmer,
    get_farmer_language,
    normalize_phone,
    update_farmer_profile,
)
from services.onboarding_state import clear_pending_name, is_pending_name

_SKIP = frozenset(
    {
        "skip",
        "later",
        "no",
        "nahi",
        "na",
        "cancel",
    }
)

_REJECT_NAMES = frozenset(
    {
        "hi",
        "hello",
        "hey",
        "ok",
        "okay",
        "yes",
        "no",
        "haan",
        "ji",
        "namaste",
    }
)

_CROP_HINTS = frozenset(
    {
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
        "mirchi",
        "gobi",
        "bhindi",
    }
)

_THANKS = {
    "hindi": "Dhanyavaad *{name}* ji! Ab aap apna sawaal bhej sakte hain. 🌾",
    "kannada": "ಧನ್ಯವಾದಗಳು *{name}* ಅವರೇ! ಈಗ ನಿಮ್ಮ ಪ್ರಶ್ನೆ ಕಳುಹಿಸಿ. 🌾",
    "english": "Thank you, *{name}*! You can send your question now. 🌾",
}


def _looks_like_name(body: str) -> bool:
    t = body.strip()
    if len(t) < 2 or len(t) > 48:
        return False
    low = t.lower()
    if low in _REJECT_NAMES or low in _CROP_HINTS:
        return False
    words = low.split()
    if len(words) > 4:
        return False
    if sum(ch.isdigit() for ch in t) > len(t) // 2:
        return False
    return True


def maybe_handle_name_onboarding(phone: str, body: str) -> str | None:
    """
    If user is pending name capture after language selection, save name or handle skip.
    """
    pid = normalize_phone(phone)
    if not get_farmer_language(pid) or not is_pending_name(pid):
        return None

    raw = (body or "").strip()
    low = raw.lower()

    if "baad mein" in low or low in _SKIP:
        clear_pending_name(pid)
        return (
            "Theek hai, naam baad mein bata dena. Koi aur madad chahiye? 🌾"
        )

    if not _looks_like_name(raw):
        return None

    name = raw.title() if raw.islower() else raw
    update_farmer_profile(pid, name=name[:80])
    clear_pending_name(pid)

    lang = get_farmer_language(pid) or "hindi"
    tmpl = _THANKS.get(lang, _THANKS["hindi"])
    return tmpl.format(name=name)


def farmer_needs_name(phone: str) -> bool:
    """True if language set but name still default placeholder."""
    pid = normalize_phone(phone)
    if not get_farmer_language(pid):
        return False
    n = (get_farmer(pid).get("name") or "").strip()
    return n in ("", "Kisan bhai")
