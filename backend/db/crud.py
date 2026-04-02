from collections.abc import Mapping, Sequence
from datetime import datetime

from sqlalchemy.future import select

from backend.db.models import Farmer


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
    if farmer and not isinstance(farmer.last_detection, dict):
        print("❌ FIXING INVALID last_detection:", farmer.last_detection)
        farmer.last_detection = {}

    created = False
    if not farmer:
        farmer = Farmer(
            phone=phone,
            location=None,
            crops=[],
            history=[],
            messages=[],
            last_detection={},
        )
        db.add(farmer)
        created = True

    if farmer:
        print(
            "🧪 Farmer last_detection AFTER FIX:",
            farmer.last_detection,
            type(farmer.last_detection),
        )
    return farmer, created


def normalize(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip().lower()
        return value or None
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


def normalize_json_list(values):
    if not values:
        return []
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
        return []
    return [normalize_json_value(value) for value in values]


def normalize_json_value(value):
    if isinstance(value, str):
        return normalize(value)
    if isinstance(value, Mapping):
        return {str(key): normalize_json_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [normalize_json_value(item) for item in value]
    return value


def build_detection_payload(disease_result):
    if not disease_result:
        return None

    if isinstance(disease_result, Mapping):
        disease_name = disease_result.get("disease")
        severity = (
            (disease_result.get("severity") or {}).get("level")
            if isinstance(disease_result.get("severity"), Mapping)
            else disease_result.get("severity", "unknown")
        )
    else:
        disease_name = disease_result
        severity = "unknown"

    if not disease_name:
        return None

    return {
        "disease": str(disease_name).lower(),
        "date": datetime.utcnow().isoformat(),
        "severity": severity if severity else "unknown",
    }


def normalize_detection(detection):
    if not detection:
        return {}
    if isinstance(detection, str):
        disease = normalize(detection)
        payload = build_detection_payload({"disease": disease})
        return payload if payload else {}
    if isinstance(detection, Mapping):
        normalized = {
            str(key): normalize_json_value(value)
            for key, value in detection.items()
            if value is not None
        }
        disease = normalize(normalized.get('disease'))
        if disease:
            normalized['disease'] = disease
        elif 'disease' in normalized:
            normalized.pop('disease', None)
        return normalized
    return {}


def extract_recent_disease(last_detection):
    if isinstance(last_detection, Mapping):
        return normalize(last_detection.get('disease'))
    if isinstance(last_detection, str):
        return normalize(last_detection)
    return None


async def upsert_farmer(
    db,
    phone,
    location=None,
    language=None,
    name=None,
    soil_type=None,
    history=None,
    messages=None,
    last_seen=None,
    last_detection=None,
):
    farmer, created = await _get_or_create_farmer(db, phone)
    if not farmer:
        return None

    print("🧪 UPSERT farmer, NOT touching last_detection")
    changed = created

    updates = {
        'name': normalize(name),
        'location': normalize(location),
        'soil_type': normalize(soil_type),
    }

    for field, value in updates.items():
        if value is not None and getattr(farmer, field) != value:
            setattr(farmer, field, value)
            changed = True

    if history is not None:
        normalized_history = normalize_json_list(history)
        if (farmer.history or []) != normalized_history:
            farmer.history = normalized_history
            changed = True

    if messages is not None:
        normalized_messages = normalize_json_list(messages)
        if (farmer.messages or []) != normalized_messages:
            farmer.messages = normalized_messages
            changed = True

    if last_seen is not None and farmer.last_seen != last_seen:
        farmer.last_seen = last_seen
        changed = True

    if changed:
        if not isinstance(farmer.last_detection, dict):
            print("❌ FIXING INVALID last_detection:", farmer.last_detection)
            farmer.last_detection = {}
        print("📦 Saving last_detection:", farmer.last_detection, type(farmer.last_detection))
        await db.commit()
        await db.refresh(farmer)

    return farmer


async def add_crop(db, phone, crop):
    crop = normalize(crop)
    if not crop:
        return None

    farmer, created = await _get_or_create_farmer(db, phone)
    if not farmer:
        return None

    crops = normalize_list(farmer.crops)
    if crop in crops:
        if created:
            await db.commit()
            await db.refresh(farmer)
        return farmer

    farmer.crops = [*crops, crop]
    await db.commit()
    await db.refresh(farmer)
    return farmer


async def add_disease(db, farmer_id, disease_result):
    result = await db.execute(select(Farmer).where(Farmer.phone == farmer_id))
    farmer = result.scalar_one_or_none()

    if not farmer:
        return

    payload = build_detection_payload(disease_result)

    print("🧪 FINAL PAYLOAD:", payload, type(payload))

    if not isinstance(farmer.last_detection, dict):
        print("❌ FIXING INVALID last_detection:", farmer.last_detection)
        farmer.last_detection = {}

    if isinstance(payload, str):
        raise ValueError("❌ last_detection received STRING")

    if payload:
        farmer.last_detection = payload

        history = farmer.history or []
        history.append(payload)
        farmer.history = history[-10:]

    print("📦 Saving last_detection:", farmer.last_detection, type(farmer.last_detection))

    await db.commit()
    await db.refresh(farmer)
    return farmer


async def get_farmer_profile(db, phone):
    farmer = await _get_farmer(db, phone)
    crops = normalize_list(farmer.crops if farmer else [])
    recent_disease = extract_recent_disease(farmer.last_detection if farmer else None)

    return {
        'farmer': farmer,
        'crops': crops,
        'recent_disease': recent_disease,
    }
