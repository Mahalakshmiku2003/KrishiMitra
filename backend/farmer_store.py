"""
farmer_store.py
Fixed: SQL uses %s style params throughout, no mixing of :name and %(name)s
"""

import json
from datetime import date
from sqlalchemy import text
from services.db import SessionLocal


def get_farmer(phone: str) -> dict:
    with SessionLocal() as db:
        result = db.execute(
            text("SELECT phone, name, crops, location, soil_type, history, messages FROM farmers WHERE phone = :phone"),
            {"phone": phone}
        ).fetchone()

        if not result:
            db.execute(
                text("INSERT INTO farmers (phone) VALUES (:phone) ON CONFLICT DO NOTHING"),
                {"phone": phone}
            )
            db.commit()
            result = db.execute(
                text("SELECT phone, name, crops, location, soil_type, history, messages FROM farmers WHERE phone = :phone"),
                {"phone": phone}
            ).fetchone()

    return {
        "phone":     result[0],
        "name":      result[1] or "Kisan bhai",
        "crops":     result[2] or [],
        "location":  result[3] or "India",
        "soil_type": result[4] or "unknown",
        "history":   result[5] or [],
        "messages":  result[6] or [],
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