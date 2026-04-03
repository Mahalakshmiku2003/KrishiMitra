from sqlalchemy import text
from backend.services.db import SessionLocal


def get_farmer_location(phone: str) -> dict | None:
    with SessionLocal() as db:
        result = db.execute(
            text("SELECT lat, lng FROM farmers WHERE phone = :phone"),
            {"phone": phone.strip().lower()},
        ).fetchone()

    if result and result[0] is not None and result[1] is not None:
        return {"lat": float(result[0]), "lng": float(result[1])}
    return None


def save_farmer_location(phone: str, lat: float, lng: float):
    with SessionLocal() as db:
        db.execute(
            text(
                """
                INSERT INTO farmers (phone, lat, lng, last_detection, history, messages, crops, language)
                VALUES (:phone, :lat, :lng, '{}'::jsonb, '[]'::jsonb, '[]'::jsonb, '{}'::text[], NULL)
                ON CONFLICT (phone) DO UPDATE
                SET lat = :lat, lng = :lng, last_seen = NOW()
                """
            ),
            {
                "phone": phone.strip().lower(),
                "lat": float(lat),
                "lng": float(lng),
            },
        )
        db.commit()


def _normalize_price_alert_params(
    phone: str, commodity: str, target_price: float, direction: str
) -> dict:
    return {
        "phone": phone.strip().lower(),
        "commodity": commodity.strip().lower(),
        "target_price": float(target_price),
        "direction": direction.strip().lower(),
    }


def save_price_alert(phone: str, commodity: str, target_price: float, direction: str):
    phone = phone.strip().lower()
    commodity = commodity.strip().lower()
    direction = direction.strip().lower()
    target_price = float(target_price)

    with SessionLocal() as db:
        existing = db.execute(
            text(
                """
                SELECT id
                FROM price_alerts
                WHERE phone = :phone
                  AND commodity = :commodity
                  AND target_price = :target_price
                  AND direction = :direction
                  AND active = TRUE
                LIMIT 1
                """
            ),
            {
                "phone": phone,
                "commodity": commodity,
                "target_price": target_price,
                "direction": direction,
            },
        ).fetchone()

        if existing:
            return {"created": False, "message": "already_exists"}

        db.execute(
            text(
                """
                INSERT INTO price_alerts (phone, commodity, target_price, direction)
                VALUES (:phone, :commodity, :target_price, :direction)
                """
            ),
            {
                "phone": phone,
                "commodity": commodity,
                "target_price": target_price,
                "direction": direction,
            },
        )
        db.commit()

    return {"created": True, "message": "created"}


def get_active_alerts() -> list:
    with SessionLocal() as db:
        rows = db.execute(
            text(
                """
                SELECT id, phone, commodity, target_price, direction
                FROM price_alerts
                WHERE active = TRUE
                """
            )
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
