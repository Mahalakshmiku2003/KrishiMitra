"""
farmer_store.py
Fixed: SQL uses named params throughout, no mixing of styles.

Merge notes:
- save_last_detection: uses theirs (jsonb via build_detection_payload) —
  more robust than pipe-separated string format.
- get_last_detection: PATCH version (returns both affected_pct and bbox_pct).
- get_farmer_location / save_farmer_location: from ours.
"""

import json
from datetime import date, datetime
from sqlalchemy import text
from services.db import SessionLocal

from backend.db.crud import build_detection_payload


def get_farmer(phone: str) -> dict:
    with SessionLocal() as db:
        result = db.execute(
            text(
                "SELECT phone, name, crops, location, soil_type, history, messages FROM farmers WHERE phone = :phone"
            ),
            {"phone": phone},
        ).fetchone()

        if not result:
            db.execute(
                text(
                    "INSERT INTO farmers (phone) VALUES (:phone) ON CONFLICT DO NOTHING"
                ),
                {"phone": phone},
            )
            db.commit()
            result = db.execute(
                text(
                    "SELECT phone, name, crops, location, soil_type, history, messages FROM farmers WHERE phone = :phone"
                ),
                {"phone": phone},
            ).fetchone()

    return {
        "phone": result[0],
        "name": result[1] or "Kisan bhai",
        "crops": result[2] or [],
        "location": result[3] or "India",
        "soil_type": result[4] or "unknown",
        "history": result[5] or [],
        "messages": result[6] or [],
    }


def save_message(phone: str, user_msg: str, bot_msg: str):
    new_msgs = json.dumps(
        [
            {"role": "user", "content": user_msg},
            {"role": "assistant", "content": bot_msg},
        ]
    )
    with SessionLocal() as db:
        db.execute(
            text("""
                UPDATE farmers
                SET
                    messages  = COALESCE(messages, '[]'::jsonb) || cast(:new_msgs as jsonb),
                    last_seen = NOW()
                WHERE phone = :phone
            """),
            {"new_msgs": new_msgs, "phone": phone},
        )
        db.commit()


def update_farmer_profile(phone: str, **kwargs):
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
            values,
        )
        db.commit()


def add_to_history(phone: str, issue: str, treatment: str):
    event = json.dumps(
        [{"date": str(date.today()), "issue": issue, "treatment": treatment}]
    )
    with SessionLocal() as db:
        db.execute(
            text("""
                UPDATE farmers
                SET history = COALESCE(history, '[]'::jsonb) || cast(:event as jsonb)
                WHERE phone = :phone
            """),
            {"event": event, "phone": phone},
        )
        db.commit()


def save_last_detection(phone: str, bbox_pct: float, severity: str):
    """Stores detection as jsonb via build_detection_payload."""
    payload = build_detection_payload(
        {"disease": "unknown", "severity": {"level": severity or "unknown"}}
    )
    print("🧪 FINAL last_detection VALUE:", payload, type(payload))
    if isinstance(payload, str):
        raise ValueError("❌ last_detection STILL STRING")
    detection_data = json.dumps(
        {**(payload or {}), "bbox_pct": bbox_pct, "affected_pct": bbox_pct}
    )
    with SessionLocal() as db:
        db.execute(
            text("""
                UPDATE farmers
                SET last_detection = cast(:detection_data as jsonb)
                WHERE phone = :phone
            """),
            {"detection_data": detection_data, "phone": phone},
        )
        db.commit()


def get_last_detection(phone: str) -> dict:
    """
    Returns both affected_pct and bbox_pct (same value) so callers
    using either key name work correctly.
    """
    try:
        with SessionLocal() as db:
            result = db.execute(
                text("SELECT last_detection FROM farmers WHERE phone = :phone"),
                {"phone": phone},
            ).fetchone()

        if result and result[0]:
            detection = result[0] if isinstance(result[0], dict) else {}
            affected_pct = float(
                detection.get("affected_pct", detection.get("bbox_pct", 20.0))
            )
            severity = detection.get("severity", "unknown")
            return {
                "affected_pct": affected_pct,
                "bbox_pct": affected_pct,
                "severity": severity,
            }
    except Exception as e:
        print(f"[FarmerStore] get_last_detection error: {e}")

    return {"affected_pct": 20.0, "bbox_pct": 20.0, "severity": "unknown"}


def get_farmer_location(phone: str) -> dict | None:
    """Returns saved lat/lng or None if not set yet."""
    with SessionLocal() as db:
        result = db.execute(
            text("SELECT lat, lng FROM farmers WHERE phone = :phone"),
            {"phone": phone},
        ).fetchone()

    if result and result[0] is not None and result[1] is not None:
        return {"lat": result[0], "lng": result[1]}
    return None


def save_farmer_location(phone: str, lat: float, lng: float):
    """Save farmer's GPS location permanently."""
    with SessionLocal() as db:
        db.execute(
            text("""
                INSERT INTO farmers (phone, lat, lng)
                VALUES (:phone, :lat, :lng)
                ON CONFLICT (phone) DO UPDATE
                SET lat = :lat, lng = :lng, last_seen = NOW()
            """),
            {"phone": phone, "lat": lat, "lng": lng},
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
            {
                "phone": phone,
                "commodity": commodity,
                "target_price": target_price,
                "direction": direction,
            },
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
        {
            "id": r[0],
            "phone": r[1],
            "commodity": r[2],
            "target_price": float(r[3]),
            "direction": r[4],
        }
        for r in rows
    ]


def deactivate_alert(alert_id: int):
    with SessionLocal() as db:
        db.execute(
            text("UPDATE price_alerts SET active = FALSE WHERE id = :id"),
            {"id": alert_id},
        )
        db.commit()
