from sqlalchemy.orm import Session
from math import radians, cos, sin, asin, sqrt
from sqlalchemy import text

def get_all_farmers(db: Session):
    return db.execute(text("SELECT * FROM farmers")).mappings().all()


def get_nearby_farmers(db: Session, lat, lng, radius_km=50):
    farmers = get_all_farmers(db)
    nearby = []

    for f in farmers:
        if f["lat"] is None or f["lng"] is None:
            continue

        dist = distance_km(lat, lng, f["lat"], f["lng"])
        if dist <= radius_km:
            nearby.append(f)

    return nearby


def distance_km(lat1, lon1, lat2, lon2):
    dlon = radians(lon2 - lon1)
    dlat = radians(lat1 - lat2)

    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))

    return 6371 * c