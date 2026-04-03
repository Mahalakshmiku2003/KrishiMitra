from datetime import datetime, timezone

from backend.db.database import AsyncSessionLocal
from backend.db.crud import _get_or_create_farmer

# kept only for backward compatibility; no longer the source of truth
_pending_location: dict = {}

_PENDING_ROLE = "system_pending"
_PENDING_TYPE = "pending_location"


def _normalize_phone(phone: str) -> str:
    return (phone or "").strip().lower()


def _is_pending_location_message(item: dict) -> bool:
    return (
        isinstance(item, dict)
        and item.get("role") == _PENDING_ROLE
        and item.get("type") == _PENDING_TYPE
    )


async def set_pending_location_action(
    phone: str,
    commodity: str | None = None,
    language: str = "Hindi",
    reason: str = "mandi",
):
    phone = _normalize_phone(phone)
    db = AsyncSessionLocal()
    try:
        farmer, _ = await _get_or_create_farmer(db, phone)
        messages = list(farmer.messages or [])

        messages = [m for m in messages if not _is_pending_location_message(m)]
        messages.append(
            {
                "role": _PENDING_ROLE,
                "type": _PENDING_TYPE,
                "commodity": commodity,
                "language": language or "Hindi",
                "reason": reason,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
        )

        farmer.messages = messages[-50:]
        await db.commit()
    finally:
        await db.close()


async def get_pending_location_action(phone: str) -> dict | None:
    phone = _normalize_phone(phone)
    db = AsyncSessionLocal()
    try:
        farmer, _ = await _get_or_create_farmer(db, phone)
        messages = list(farmer.messages or [])

        for item in reversed(messages):
            if _is_pending_location_message(item):
                return item
        return None
    finally:
        await db.close()


async def clear_pending_location_action(phone: str) -> dict | None:
    phone = _normalize_phone(phone)
    db = AsyncSessionLocal()
    try:
        farmer, _ = await _get_or_create_farmer(db, phone)
        messages = list(farmer.messages or [])

        pending = None
        kept = []
        for item in messages:
            if _is_pending_location_message(item):
                pending = item
            else:
                kept.append(item)

        farmer.messages = kept[-50:]
        await db.commit()
        return pending
    finally:
        await db.close()
