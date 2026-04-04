import math
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.services.db import SessionLocal
from backend.services.whatsapp_service import send_proactive_message

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


def get_all_farmers(db: Session) -> list[dict[str, Any]]:
    rows = db.execute(
        text("SELECT phone, lat, lng, crops FROM farmers")
    ).fetchall()
    return [
        {"phone": r[0], "lat": r[1], "lng": r[2], "crops": r[3]}
        for r in rows
    ]


def get_nearby_farmers(
    db: Session,
    lat: float,
    lng: float,
    radius_km: float,
    exclude_phone: str,
) -> list[dict[str, Any]]:
    rows = db.execute(
        text(
            """
            SELECT phone, lat, lng, crops FROM farmers
            WHERE lat IS NOT NULL AND lng IS NOT NULL
            """
        )
    ).fetchall()
    ex = _normalize_phone(exclude_phone)
    out: list[dict[str, Any]] = []
    for r in rows:
        f = {"phone": r[0], "lat": r[1], "lng": r[2], "crops": r[3]}
        fp = _normalize_phone(str(f.get("phone") or ""))
        if not fp or fp == ex:
            continue
        plat, plng = f.get("lat"), f.get("lng")
        if plat is None or plng is None:
            continue
        dist = _haversine_km(lat, lng, float(plat), float(plng))
        if dist <= radius_km:
            f["_dist_km"] = dist
            out.append(f)
    return out


def _mark_processed(db: Session, det_id: Any) -> None:
    if det_id is None:
        return
    db.execute(
        text("UPDATE detections SET processed = true WHERE id = :id"),
        {"id": det_id},
    )
    db.commit()


async def handle_new_detection(
    db: Optional[Session], detection: dict[str, Any]
) -> dict[str, Any]:
    print("🔥 OUTBREAK TRIGGER:", detection)

    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    det_id = detection.get("id")

    try:
        sev = detection.get("severity")
        if sev is None:
            print("❌ Invalid severity")
            _mark_processed(db, det_id)
            return {"status": "invalid"}

        try:
            sev = int(sev)
        except (TypeError, ValueError):
            print("❌ Invalid severity")
            _mark_processed(db, det_id)
            return {"status": "invalid"}

        if sev <= 5:
            print("❌ Severity too low")
            _mark_processed(db, det_id)
            return {"status": "low"}

        if not detection.get("spread"):
            print("❌ Spread false")
            _mark_processed(db, det_id)
            return {"status": "no_spread"}

        reporter = _normalize_phone(str(detection.get("phone") or ""))
        disease = (detection.get("disease_name") or "unknown").strip()
        det_crop = (detection.get("crop_type") or "").strip().lower()

        lat0 = detection.get("lat")
        lng0 = detection.get("lng")
        try:
            if lat0 is None or lng0 is None:
                lat_f = lng_f = None
            else:
                lat_f, lng_f = float(lat0), float(lng0)
        except (TypeError, ValueError):
            lat_f = lng_f = None

        if lat_f is None or lng_f is None:
            print("❌ Missing detection coordinates")
            _mark_processed(db, det_id)
            return {"status": "no_coords"}

        all_farmers = get_all_farmers(db)
        print(f"👥 Total farmers: {len(all_farmers)}")

        nearby_farmers = get_nearby_farmers(
            db, lat_f, lng_f, NEARBY_RADIUS_KM, reporter
        )
        print(f"📍 Nearby farmers: {len(nearby_farmers)}")

        target_farmers: list[dict[str, Any]] = []
        other_farmers: list[dict[str, Any]] = []
        if not det_crop:
            target_farmers = list(nearby_farmers)
        else:
            for f in nearby_farmers:
                crops_raw = f.get("crops")
                if isinstance(crops_raw, (list, tuple)):
                    farmer_crops = ",".join(str(x) for x in crops_raw).lower()
                else:
                    farmer_crops = (str(crops_raw) if crops_raw is not None else "").lower()
                if det_crop in farmer_crops:
                    target_farmers.append(f)
                else:
                    other_farmers.append(f)

        print(f"🎯 Same crop farmers: {len(target_farmers)}")
        print(f"🌐 Other farmers: {len(other_farmers)}")

        to_alert = target_farmers if target_farmers else other_farmers

        if not nearby_farmers:
            try:
                await send_proactive_message(
                    _normalize_phone(str(detection.get("phone") or "")),
                    "🔥 Test outbreak alert triggered",
                )
                print(
                    "✅ Sent:",
                    _normalize_phone(str(detection.get("phone") or "")),
                )
            except Exception as e:
                print("❌ Failed:", e)
            _mark_processed(db, det_id)
            return {"status": "test_alert_sent"}

        msg_template = (
            f"⚠️ *KrishiMitra outbreak alert*\n\n"
            f"A disease (*{disease}*) was reported near you"
            + (f" ({det_crop})" if det_crop else "")
            + ".\n\n"
            f"Please inspect your fields and share a photo if you see symptoms. 🌾"
        )

        for farmer in to_alert:
            try:
                await send_proactive_message(farmer["phone"], msg_template)
                print("✅ Sent:", farmer["phone"])
            except Exception as e:
                print("❌ Failed:", e)

        _mark_processed(db, det_id)
        return {"status": "ok"}
    except Exception as e:
        print("Outbreak error:", e)
        try:
            db.rollback()
        except Exception:
            pass
        return {"status": "error", "detail": str(e)}
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
