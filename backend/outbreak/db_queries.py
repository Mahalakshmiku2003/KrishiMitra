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

import math

def get_direction(lat1, lon1, lat2, lon2):
    """
    Returns direction from farmer → outbreak
    """
    dlon = math.radians(lon2 - lon1)

    y = math.sin(dlon) * math.cos(math.radians(lat2))
    x = (
        math.cos(math.radians(lat1)) * math.sin(math.radians(lat2))
        - math.sin(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.cos(dlon)
    )

    bearing = math.degrees(math.atan2(y, x))
    bearing = (bearing + 360) % 360

    directions = [
        "North", "North-East", "East", "South-East",
        "South", "South-West", "West", "North-West"
    ]

    index = round(bearing / 45) % 8
    return directions[index]