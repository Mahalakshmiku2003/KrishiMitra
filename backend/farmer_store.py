"""
farmer_store.py
Fixed: SQL uses %s style params throughout, no mixing of :name and %(name)s
"""

import json
from datetime import date, datetime, timezone
from sqlalchemy import text
from services.db import SessionLocal


def normalize_phone(phone: str) -> str:
    return (phone or "").replace("whatsapp:", "").strip()


def get_farmer_language(phone: str) -> str | None:
    """Returns stored language code (hindi/kannada/english) or None if unset."""
    pid = normalize_phone(phone)
    with SessionLocal() as db:
        row = db.execute(
            text("SELECT language FROM farmers WHERE phone = :phone"),
            {"phone": pid},
        ).fetchone()
    if not row or row[0] is None:
        return None
    s = str(row[0]).strip()
    return s if s else None


def record_detection_if_outbreak(phone: str, disease_result: dict) -> None:
    """
    Insert into detections when severity_score > 5 and disease spreads (per progression DB).
    Requires farmers row for FK — ensured via get_farmer.
    """
    if not disease_result or disease_result.get("error"):
        return
    sev = disease_result.get("severity_score")
    spreads = disease_result.get("spread")
    if sev is None or sev <= 5 or not spreads:
        return

    pid = normalize_phone(phone)
    get_farmer(pid)  # ensure FK target exists

    disease_name = disease_result.get("disease") or "Unknown"
    crop_type = disease_result.get("crop") or "Unknown"
    loc = get_farmer_location(pid)
    lat = loc["lat"] if loc else None
    lng = loc["lng"] if loc else None

    with SessionLocal() as db:
        db.execute(
            text(
                """
                INSERT INTO detections
                    (phone, disease_name, crop_type, severity, lat, lng, spread)
                VALUES
                    (:phone, :disease_name, :crop_type, :severity, :lat, :lng, :spread)
                """
            ),
            {
                "phone": pid,
                "disease_name": disease_name,
                "crop_type": crop_type,
                "severity": int(sev),
                "lat": lat,
                "lng": lng,
                "spread": True,
            },
        )
        db.commit()

    try:
        from scheduler import schedule_disease_followup_series

        schedule_disease_followup_series(pid, disease_name, crop_type)
    except Exception as e:
        print(f"[FarmerStore] schedule_disease_followup_series: {e}")


def set_farmer_language(phone: str, language: str) -> None:
    """Persist language on farmers row (upserts phone row if missing)."""
    pid = normalize_phone(phone)
    lang = (language or "").strip().lower()
    if not lang:
        return
    with SessionLocal() as db:
        db.execute(
            text(
                """
                INSERT INTO farmers (phone, language, last_seen)
                VALUES (:phone, :language, NOW())
                ON CONFLICT (phone) DO UPDATE
                SET language = EXCLUDED.language, last_seen = NOW()
                """
            ),
            {"phone": pid, "language": lang},
        )
        db.commit()


def save_farmer_diagnosis(phone: str, disease_result: dict, user_message: str) -> None:
    """
    Persist latest diseased-crop analysis on farmers (last_detection JSON + history).
    Skips healthy / errors / missing disease.
    """
    if not disease_result or disease_result.get("error"):
        return
    raw = (disease_result.get("raw_name") or "").lower()
    if "healthy" in raw:
        return

    pid = normalize_phone(phone)
    get_farmer(pid)

    sev = disease_result.get("severity") or {}
    prog = disease_result.get("progression") or {}
    payload = {
        "disease": disease_result.get("disease"),
        "crop_model": disease_result.get("crop"),
        "crop_from_message": (user_message or "").strip()[:200] or None,
        "severity_level": sev.get("level"),
        "severity_description": sev.get("description"),
        "severity_score": disease_result.get("severity_score"),
        "spread": disease_result.get("spread"),
        "confidence": disease_result.get("confidence"),
        "bbox_pct": disease_result.get("bbox_pct"),
        "progression": prog,
        "urgency": disease_result.get("urgency"),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    payload_json = json.dumps(payload, ensure_ascii=False)

    issue = str(disease_result.get("disease") or "Crop disease")
    treatment = (
        f"Severity {sev.get('level', '?')} (score {disease_result.get('severity_score', '?')}); "
        f"urgency: {disease_result.get('urgency') or '—'}"
    )

    with SessionLocal() as db:
        db.execute(
            text("""
                UPDATE farmers
                SET last_detection = cast(:payload as jsonb),
                    last_seen = NOW()
                WHERE phone = :phone
            """),
            {"payload": payload_json, "phone": pid},
        )
        db.commit()

    add_to_history(pid, issue, treatment)


def get_farmer(phone: str) -> dict:
    phone = normalize_phone(phone)
    with SessionLocal() as db:
        result = db.execute(
            text(
                "SELECT phone, name, crops, location, soil_type, history, messages, language "
                "FROM farmers WHERE phone = :phone"
            ),
            {"phone": phone},
        ).fetchone()

        if not result:
            db.execute(
                text("INSERT INTO farmers (phone) VALUES (:phone) ON CONFLICT DO NOTHING"),
                {"phone": phone},
            )
            db.commit()
            result = db.execute(
                text(
                    "SELECT phone, name, crops, location, soil_type, history, messages, language "
                    "FROM farmers WHERE phone = :phone"
                ),
                {"phone": phone},
            ).fetchone()

    return {
        "phone":     result[0],
        "name":      result[1] or "Kisan bhai",
        "crops":     result[2] or [],
        "location":  result[3] or "India",
        "soil_type": result[4] or "unknown",
        "history":   result[5] or [],
        "messages":  result[6] or [],
        "language":  result[7] if len(result) > 7 else None,
    }


def save_message(phone: str, user_msg: str, bot_msg: str):
    """
    Fixed: cast done in Python, not in SQL — avoids the :new_msgs::jsonb syntax error.
    """
    new_msgs = json.dumps([
        {"role": "user",      "content": user_msg},
        {"role": "assistant", "content": bot_msg},
    ])
    with SessionLocal() as db:
        db.execute(
            text("""
                UPDATE farmers
                SET
                    messages  = COALESCE(messages, '[]'::jsonb) || cast(:new_msgs as jsonb),
                    last_seen = NOW()
                WHERE phone = :phone
            """),
            {"new_msgs": new_msgs, "phone": phone}
        )
        db.commit()


def update_farmer_profile(phone: str, **kwargs):
    phone = normalize_phone(phone)
    allowed = {"name", "crops", "location", "soil_type"}
    fields, values = [], {"phone": phone}

    for key, val in kwargs.items():
        if key in allowed and val is not None:
            fields.append(f"{key} = :{key}")
            values[key] = val

    if not fields:
        return

    with SessionLocal() as db:
        db.execute(
            text(f"UPDATE farmers SET {', '.join(fields)} WHERE phone = :phone"),
            values
        )
        db.commit()


def add_to_history(phone: str, issue: str, treatment: str):
    phone = normalize_phone(phone)
    event = json.dumps([{
        "date":      str(date.today()),
        "issue":     issue,
        "treatment": treatment,
    }])
    with SessionLocal() as db:
        db.execute(
            text("""
                UPDATE farmers
                SET history = COALESCE(history, '[]'::jsonb) || cast(:event as jsonb)
                WHERE phone = :phone
            """),
            {"event": event, "phone": phone}
        )
        db.commit()


def _parse_last_detection_row(raw) -> dict:
    """Support jsonb object, JSON string, or legacy 'bbox|severity' text."""
    defaults = {"affected_pct": 20.0, "bbox_pct": 20.0, "severity": "unknown"}
    if raw is None:
        return dict(defaults)

    if isinstance(raw, dict):
        data = raw
    elif isinstance(raw, str):
        raw = raw.strip()
        if "|" in raw and not raw.startswith("{"):
            parts = raw.split("|", 1)
            try:
                pct = float(parts[0])
            except ValueError:
                pct = 20.0
            sev = parts[1] if len(parts) > 1 else "unknown"
            return {
                "affected_pct": pct,
                "bbox_pct": pct,
                "severity": sev,
            }
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return dict(defaults)
    else:
        return dict(defaults)

    if not isinstance(data, dict):
        return dict(defaults)

    bbox = data.get("bbox_pct")
    if bbox is None:
        bbox = 20.0
    try:
        bbox = float(bbox)
    except (TypeError, ValueError):
        bbox = 20.0
    sev = data.get("severity_level") or data.get("severity") or "unknown"
    if isinstance(sev, dict):
        sev = sev.get("level", "unknown")
    return {
        "affected_pct": bbox,
        "bbox_pct": bbox,
        "severity": str(sev),
        "diagnosis": data,
    }


def get_last_detection(phone: str) -> dict:
    """Last crop diagnosis: legacy pipe format or JSON from save_farmer_diagnosis."""
    phone = normalize_phone(phone)
    try:
        with SessionLocal() as db:
            result = db.execute(
                text("SELECT last_detection FROM farmers WHERE phone = :phone"),
                {"phone": phone},
            ).fetchone()
        if result and result[0] is not None:
            return _parse_last_detection_row(result[0])
    except Exception as e:
        print(f"[FarmerStore] get_last_detection error: {e}")

    return {
        "affected_pct": 20.0,
        "bbox_pct": 20.0,
        "severity": "unknown",
    }


# Add these two functions to farmer_store.py

def get_farmer_location(phone: str) -> dict | None:
    """Returns saved lat/lng or None if not set yet."""
    phone = normalize_phone(phone)
    with SessionLocal() as db:
        result = db.execute(
            text("SELECT lat, lng FROM farmers WHERE phone = :phone"),
            {"phone": phone}
        ).fetchone()
    
    if result and result[0] is not None and result[1] is not None:
        return {"lat": result[0], "lng": result[1]}
    return None


def save_farmer_location(phone: str, lat: float, lng: float):
    """Save farmer's home location permanently."""
    phone = normalize_phone(phone)
    with SessionLocal() as db:
        db.execute(
            text("""
                INSERT INTO farmers (phone, lat, lng)
                VALUES (:phone, :lat, :lng)
                ON CONFLICT (phone) DO UPDATE
                SET lat = :lat, lng = :lng, last_seen = NOW()
            """),
            {"phone": phone, "lat": lat, "lng": lng}
        )
        db.commit()
    print(f"[FarmerStore] Saved location for {phone}: {lat}, {lng}")

def save_price_alert(phone: str, commodity: str, target_price: float, direction: str):
    with SessionLocal() as db:
        db.execute(
            text("""
                INSERT INTO price_alerts (phone, commodity, target_price, direction)
                VALUES (:phone, :commodity, :target_price, :direction)
            """),
            {"phone": phone, "commodity": commodity,
             "target_price": target_price, "direction": direction}
        )
        db.commit()
    print(f"[Alert] Saved: {phone} wants {commodity} {direction} Rs.{target_price}")


def get_active_alerts() -> list:
    with SessionLocal() as db:
        rows = db.execute(
            text("""
                SELECT id, phone, commodity, target_price, direction
                FROM price_alerts WHERE active = TRUE
            """)
        ).fetchall()
    return [
        {"id": r[0], "phone": r[1], "commodity": r[2],
         "target_price": float(r[3]), "direction": r[4]}
        for r in rows
    ]


def deactivate_alert(alert_id: int):
    with SessionLocal() as db:
        db.execute(
            text("UPDATE price_alerts SET active = FALSE WHERE id = :id"),
            {"id": alert_id}
        )
        db.commit()