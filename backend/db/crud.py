from collections.abc import Mapping, Sequence
from datetime import datetime, timezone

from sqlalchemy.future import select

from backend.db.models import Farmer, InboundMessage


def normalize(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        return value.lower()
    return value


def normalize_list(values):
    if not values:
        return []

    normalized = []
    seen = set()
    for value in values:
        item = normalize(value)
        if item and item not in seen:
            normalized.append(item)
            seen.add(item)
    return normalized


def normalize_json_value(value):
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, Mapping):
        return {str(key): normalize_json_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [normalize_json_value(item) for item in value]
    return value


def normalize_json_list(values):
    if not values:
        return []
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
        return []
    return [normalize_json_value(value) for value in values]


def build_detection_payload(disease_result):
    if not disease_result:
        return None

    if isinstance(disease_result, Mapping):
        disease_name = disease_result.get("disease")
        severity_obj = disease_result.get("severity") or {}
        severity = (
            severity_obj.get("level", "unknown")
            if isinstance(severity_obj, Mapping)
            else severity_obj or "unknown"
        )
        payload = {
            "disease": str(disease_name).lower() if disease_name else None,
            "severity": severity,
            "date": datetime.now(timezone.utc).isoformat(),
        }

        if "confidence" in disease_result:
            payload["confidence"] = disease_result.get("confidence")
        if "urgency" in disease_result:
            payload["urgency"] = disease_result.get("urgency")
        if "progression" in disease_result and isinstance(
            disease_result["progression"], Mapping
        ):
            payload["progression"] = normalize_json_value(disease_result["progression"])

        if not payload["disease"]:
            return None
        return payload

    disease_name = normalize(disease_result)
    if not disease_name:
        return None

    return {
        "disease": disease_name,
        "severity": "unknown",
        "date": datetime.now(timezone.utc).isoformat(),
    }


async def _get_farmer(db, phone: str):
    phone = normalize(phone)
    if not phone:
        return None

    result = await db.execute(select(Farmer).where(Farmer.phone == phone))
    return result.scalar_one_or_none()


async def _get_or_create_farmer(db, phone: str):
    phone = normalize(phone)
    if not phone:
        return None, False

    farmer = await _get_farmer(db, phone)
    created = False

    if not farmer:
        farmer = Farmer(
            phone=phone,
            name=None,
            crops=[],
            location=None,
            history=[],
            messages=[],
            soil_type=None,
            last_detection={},
            lat=None,
            lng=None,
            language=None,
            last_seen=datetime.now(timezone.utc),
        )
        db.add(farmer)
        created = True
        await db.flush()

    if not isinstance(farmer.last_detection, dict):
        farmer.last_detection = {}

    if farmer.messages is None:
        farmer.messages = []

    if farmer.history is None:
        farmer.history = []

    if farmer.crops is None:
        farmer.crops = []

    return farmer, created


async def set_farmer_language(db, phone: str, language: str):
    farmer, _ = await _get_or_create_farmer(db, phone)
    if not farmer:
        return None

    farmer.language = language
    farmer.last_seen = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(farmer)
    return farmer


async def set_farmer_location_coords(db, phone: str, lat: float, lng: float):
    farmer, _ = await _get_or_create_farmer(db, phone)
    if not farmer:
        return None

    farmer.lat = float(lat)
    farmer.lng = float(lng)
    farmer.last_seen = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(farmer)
    return farmer


async def upsert_farmer_profile(
    db,
    phone: str,
    *,
    name=None,
    location=None,
    crop=None,
):
    farmer, _ = await _get_or_create_farmer(db, phone)
    if not farmer:
        return None

    changed = False

    name = normalize(name)
    location = normalize(location)
    crop = normalize(crop)

    if name and farmer.name != name:
        farmer.name = name
        changed = True

    if location and farmer.location != location:
        farmer.location = location
        changed = True

    if crop:
        crops = normalize_list([*(farmer.crops or []), crop])
        if crops != normalize_list(farmer.crops):
            farmer.crops = crops
            changed = True

    farmer.last_seen = datetime.now(timezone.utc)
    changed = True

    if changed:
        await db.commit()
        await db.refresh(farmer)

    return farmer


async def append_message(
    db, phone: str, role: str, content: str, max_messages: int = 20
):
    farmer, _ = await _get_or_create_farmer(db, phone)
    if not farmer:
        return None

    messages = list(farmer.messages or [])
    messages.append(
        {
            "role": role,
            "content": content,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
    )
    farmer.messages = messages[-max_messages:]
    farmer.last_seen = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(farmer)
    return farmer


async def append_message_pair(
    db, phone: str, user_msg: str, bot_msg: str, max_messages: int = 20
):
    farmer, _ = await _get_or_create_farmer(db, phone)
    if not farmer:
        return None

    messages = list(farmer.messages or [])
    now = datetime.now(timezone.utc).isoformat()

    messages.append({"role": "user", "content": user_msg, "ts": now})
    messages.append({"role": "assistant", "content": bot_msg, "ts": now})

    farmer.messages = messages[-max_messages:]
    farmer.last_seen = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(farmer)
    return farmer


async def add_disease(db, phone: str, disease_result):
    farmer, _ = await _get_or_create_farmer(db, phone)
    if not farmer:
        return None

    payload = build_detection_payload(disease_result)
    if not payload:
        return farmer

    farmer.last_detection = payload

    history = list(farmer.history or [])
    history.append(payload)
    farmer.history = history[-10:]

    farmer.last_seen = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(farmer)
    return farmer


async def get_recent_messages(db, phone: str, limit: int = 10):
    farmer = await _get_farmer(db, phone)
    if not farmer:
        return []
    return list(farmer.messages or [])[-limit:]


async def get_farmer_profile(db, phone: str):
    farmer = await _get_farmer(db, phone)

    return {
        "farmer": farmer,
        "crops": normalize_list(farmer.crops if farmer else []),
        "recent_disease": (
            farmer.last_detection.get("disease")
            if farmer and isinstance(farmer.last_detection, dict)
            else None
        ),
    }


async def reserve_inbound_message(
    db,
    provider_message_id: str | None,
    phone: str,
    body: str | None = None,
):
    """
    Idempotency guard.

    Returns:
    - {"state": "new"} if this is a new inbound message and caller should process it
    - {"state": "duplicate_done", "response_xml": "..."} if already processed
    - {"state": "duplicate_inflight"} if same message is already being processed
    """
    if not provider_message_id:
        return {"state": "new"}

    result = await db.execute(
        select(InboundMessage).where(
            InboundMessage.provider_message_id == provider_message_id
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        if existing.response_xml:
            return {
                "state": "duplicate_done",
                "response_xml": existing.response_xml,
            }
        return {"state": "duplicate_inflight"}

    inbound = InboundMessage(
        provider_message_id=provider_message_id,
        phone=normalize(phone) or phone,
        body=body,
        status="processing",
    )
    db.add(inbound)
    await db.commit()
    return {"state": "new"}


async def finalize_inbound_message(
    db,
    provider_message_id: str | None,
    response_xml: str,
    status: str = "processed",
):
    if not provider_message_id:
        return

    result = await db.execute(
        select(InboundMessage).where(
            InboundMessage.provider_message_id == provider_message_id
        )
    )
    inbound = result.scalar_one_or_none()
    if not inbound:
        return

    inbound.status = status
    inbound.response_xml = response_xml
    inbound.processed_at = datetime.now(timezone.utc)
    await db.commit()


async def fail_inbound_message(
    db,
    provider_message_id: str | None,
    error: str,
):
    if not provider_message_id:
        return

    result = await db.execute(
        select(InboundMessage).where(
            InboundMessage.provider_message_id == provider_message_id
        )
    )
    inbound = result.scalar_one_or_none()
    if not inbound:
        return

    inbound.status = "failed"
    inbound.error = error[:1000] if error else "unknown_error"
    inbound.processed_at = datetime.now(timezone.utc)
    await db.commit()
