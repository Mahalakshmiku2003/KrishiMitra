import math
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.services.db import SessionLocal

HIGH_SEVERITY_THRESHOLD = 65
NEARBY_RADIUS_KM = 45.0


def _haversine_km(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    )
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def _normalize_phone(phone: str) -> str:
    return (phone or "").replace("whatsapp:", "").strip().lower()


async def handle_new_detection(db: Optional[Session], detection: dict[str, Any]) -> None:
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    try:
        det_id = detection.get("id")
        severity = detection.get("severity")
        if severity is None:
            severity = 0
        try:
            severity = int(severity)
        except (TypeError, ValueError):
            severity = 0

        reporter = _normalize_phone(str(detection.get("phone") or ""))
        disease = (detection.get("disease_name") or "unknown").strip()
        crop = detection.get("crop_type") or ""

        lat0 = detection.get("lat")
        lng0 = detection.get("lng")
        lat_f: float | None
        lng_f: float | None
        try:
            if lat0 is None or lng0 is None:
                lat_f = lng_f = None
            else:
                lat_f, lng_f = float(lat0), float(lng0)
        except (TypeError, ValueError):
            lat_f = lng_f = None

        if severity >= HIGH_SEVERITY_THRESHOLD and lat_f is not None and lng_f is not None:
            from backend.services.whatsapp_service import send_proactive_message

            rows = db.execute(
                text(
                    """
                    SELECT phone, lat, lng FROM farmers
                    WHERE lat IS NOT NULL AND lng IS NOT NULL
                    """
                )
            ).fetchall()
            for row in rows:
                phone_raw = row[0]
                plat, plng = row[1], row[2]
                if plat is None or plng is None:
                    continue
                fp = _normalize_phone(str(phone_raw or ""))
                if not fp or fp == reporter:
                    continue
                dist = _haversine_km(lat_f, lng_f, float(plat), float(plng))
                if dist > NEARBY_RADIUS_KM:
                    continue
                phone_clean = fp.replace("whatsapp:", "").strip()
                msg = (
                    f"⚠️ *KrishiMitra outbreak alert*\n\n"
                    f"A high-severity crop disease (*{disease}*) was reported "
                    f"~{dist:.1f} km from you"
                    + (f" ({crop})" if crop else "")
                    + ".\n\n"
                    f"Please inspect your fields and share a photo if you see symptoms. 🌾"
                )
                try:
                    await send_proactive_message(phone_clean, msg)
                except Exception as e:
                    print("Outbreak error:", e)

        if det_id is not None:
            db.execute(
                text("UPDATE detections SET processed = true WHERE id = :id"),
                {"id": det_id},
            )
            db.commit()
    except Exception as e:
        print("Outbreak error:", e)
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        if close_db:
            db.close()


async def process_pending_detections() -> None:
    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT id, phone, disease_name, crop_type, severity, lat, lng, spread
                FROM detections
                WHERE processed = false
                ORDER BY id ASC
                LIMIT 100
                """
            )
        ).fetchall()
        for row in rows:
            det = {
                "id": row[0],
                "phone": row[1],
                "disease_name": row[2],
                "crop_type": row[3],
                "severity": row[4],
                "lat": row[5],
                "lng": row[6],
                "spread": row[7],
            }
            await handle_new_detection(db, det)
    except Exception as e:
        print("Outbreak error:", e)
    finally:
        db.close()
