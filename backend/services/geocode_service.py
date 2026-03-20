import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

def geocode_location(location: str) -> dict | None:
    """
    Convert a village, district or city name to lat/lng.
    Uses OpenStreetMap Nominatim — free, no API key needed.

    Returns: { "lat": float, "lng": float, "display_name": str }
    """
    params = {
        "q":              f"{location}, India",
        "format":         "json",
        "limit":          1,
        "countrycodes":   "in",   # restrict to India
    }
    headers = {
        # Nominatim requires a User-Agent
        "User-Agent": "KrishiMitra/1.0 (crop disease detection app)"
    }

    try:
        response = requests.get(NOMINATIM_URL, params=params,
                                headers=headers, timeout=10)
        results  = response.json()

        if not results:
            return None

        best = results[0]
        return {
            "lat":          float(best["lat"]),
            "lng":          float(best["lon"]),
            "display_name": best["display_name"],
        }

    except Exception as e:
        print(f"Geocoding failed for '{location}': {e}")
        return None