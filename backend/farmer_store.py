"""
farmer_store.py
Fixed: SQL uses %s style params throughout, no mixing of :name and %(name)s
"""

import json
from datetime import date, datetime, timedelta, timezone
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


def extract_stated_crop_from_text(text: str) -> str | None:
    msg = (text or "").lower()
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
        if c in msg:
            return c.capitalize()
    return None


def save_disease_diagnosis_to_farmer(
    phone: str, disease_result: dict, user_message: str
) -> bool:
    """
    Store latest disease diagnosis on farmers.last_detection (JSON) and schedule 2-day follow-ups.
    Skips healthy / errors. Returns True if a follow-up schedule was written.
    """
    if not disease_result or disease_result.get("error"):
        return False
    raw_name = (disease_result.get("raw_name") or "").lower()
    if "healthy" in raw_name:
        return False

    pid = normalize_phone(phone)
    get_farmer(pid)

    confn = float(disease_result.get("confidence_num") or 0)
    bbox_pct = round(confn * 40, 2)
    sev = disease_result.get("severity") or {}
    now = datetime.now(timezone.utc)
    next_due = (now + timedelta(days=2)).isoformat()

    payload = {
        "v": 2,
        "disease": disease_result.get("disease"),
        "pathology": disease_result.get("pathology"),
        "crop_model": disease_result.get("crop"),
        "crop_stated": extract_stated_crop_from_text(user_message),
        "bbox_pct": bbox_pct,
        "severity_level": sev.get("level"),
        "severity_description": sev.get("description"),
        "severity_score": disease_result.get("severity_score"),
        "spread": disease_result.get("spread"),
        "progression": disease_result.get("progression"),
        "urgency": disease_result.get("urgency"),
        "confidence": disease_result.get("confidence"),
        "remedies": disease_result.get("remedies"),
        "recorded_at": now.isoformat(),
        "next_followup_at": next_due,
        "followup_sent_count": 0,
    }

    j = json.dumps(payload, default=str)
    with SessionLocal() as db:
        db.execute(
            text("""
                UPDATE farmers
                SET last_detection = cast(:j as jsonb), last_seen = NOW()
                WHERE phone = :phone
            """),
            {"j": j, "phone": pid},
        )
        db.commit()

    tr = disease_result.get("remedies") or {}
    hint = ""
    for k in ("organic", "chemical"):
        for line in tr.get(k, [])[:1]:
            hint = (line or "")[:200]
            break
        if hint:
            break
    if hint:
        add_to_history(
            pid,
            str(disease_result.get("pathology") or disease_result.get("disease")),
            hint,
        )
    return True


def iter_disease_followups_due() -> list[dict]:
    """Rows whose JSON last_detection v2 has next_followup_at <= now and count < 5."""
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        rows = db.execute(
            text(
                "SELECT phone, name, language, last_detection FROM farmers "
                "WHERE last_detection IS NOT NULL"
            )
        ).fetchall()

    out: list[dict] = []
    for phone, name, language, raw in rows:
        if raw is None:
            continue
        s = raw if isinstance(raw, str) else json.dumps(raw)
        s = str(s).strip()
        if not s.startswith("{"):
            continue
        try:
            data = json.loads(s)
        except json.JSONDecodeError:
            continue
        if data.get("v") != 2:
            continue
        due_s = data.get("next_followup_at")
        if not due_s:
            continue
        try:
            due = datetime.fromisoformat(due_s.replace("Z", "+00:00"))
        except ValueError:
            continue
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        if due > now:
            continue
        if int(data.get("followup_sent_count") or 0) >= 5:
            continue
        out.append(
            {
                "phone": phone,
                "farmer_name": name or "Kisan bhai",
                "farmer_language": language,
                "snap": data,
            }
        )
    return out


def bump_disease_followup_schedule(phone: str) -> None:
    pid = normalize_phone(phone)
    with SessionLocal() as db:
        row = db.execute(
            text("SELECT last_detection FROM farmers WHERE phone = :phone"),
            {"phone": pid},
        ).fetchone()
        if not row or row[0] is None:
            return
        s = row[0] if isinstance(row[0], str) else json.dumps(row[0])
        s = str(s).strip()
        if not s.startswith("{"):
            return
        try:
            data = json.loads(s)
        except json.JSONDecodeError:
            return
        if data.get("v") != 2:
            return
        cnt = int(data.get("followup_sent_count") or 0) + 1
        data["followup_sent_count"] = cnt
        if cnt >= 5:
            data["next_followup_at"] = None
        else:
            data["next_followup_at"] = (
                datetime.now(timezone.utc) + timedelta(days=2)
            ).isoformat()
        db.execute(
            text(
                "UPDATE farmers SET last_detection = cast(:j as jsonb) WHERE phone = :phone"
            ),
            {"j": json.dumps(data, default=str), "phone": pid},
        )
        db.commit()


def record_detection_if_outbreak(
    phone: str, disease_result: dict, farmer_message: str = ""
) -> None:
    """
    Insert into detections when severity_score > 5 and disease spreads (per progression DB).
    crop_type = crop stated by farmer in the message; disease_name = diagnosed pathology only.
    """
    if not disease_result or disease_result.get("error"):
        return
    sev = disease_result.get("severity_score")
    spreads = disease_result.get("spread")
    if sev is None or sev <= 5 or not spreads:
        return

    pid = normalize_phone(phone)
    get_farmer(pid)  # ensure FK target exists

    disease_name = (disease_result.get("pathology") or "").strip() or "Unknown"
    crop_type = extract_stated_crop_from_text(farmer_message)
    if not crop_type:
        print("[Detections] Skipping insert: no crop name found in farmer message text.")
        return
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
    phone = normalize_phone(phone)
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


def save_last_detection(phone: str, bbox_pct: float, severity: str):
    """Legacy pipe format; prefer save_disease_diagnosis_to_farmer for WhatsApp flow."""
    phone = normalize_phone(phone)
    with SessionLocal() as db:
        db.execute(
            text("""
                UPDATE farmers
                SET last_detection = :detection_data
                WHERE phone = :phone
            """),
            {"detection_data": f"{bbox_pct}|{severity}", "phone": phone},
        )
        db.commit()


def get_last_detection(phone: str) -> dict:
    """Supports legacy 'bbox|severity' string or JSON v2 snapshot from save_disease_diagnosis_to_farmer."""
    phone = normalize_phone(phone)
    try:
        with SessionLocal() as db:
            result = db.execute(
                text("SELECT last_detection FROM farmers WHERE phone = :phone"),
                {"phone": phone},
            ).fetchone()

        if not result or result[0] is None:
            raise ValueError("empty")

        raw = result[0]
        s = raw if isinstance(raw, str) else json.dumps(raw)
        s = str(s).strip()
        if s.startswith("{"):
            data = json.loads(s)
            bbox = float(data.get("bbox_pct") or 20)
            sl = (data.get("severity_level") or "unknown").strip()
            return {
                "affected_pct": bbox,
                "bbox_pct": bbox,
                "severity": sl,
                "detail": data,
            }
        parts = s.split("|")
        affected_pct = float(parts[0])
        severity = parts[1] if len(parts) > 1 else "unknown"
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