# backend/agent/tools.py
import os
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Load data files
ROOT = Path(__file__).parent.parent.parent
DISEASE_DB = (
    json.loads((ROOT / "backend" / "data" / "disease_db.json").read_text())
    if (ROOT / "backend" / "data" / "disease_db.json").exists()
    else {}
)
PROGRESSION_DB = (
    json.loads((ROOT / "backend" / "data" / "progression_db.json").read_text())
    if (ROOT / "backend" / "data" / "progression_db.json").exists()
    else {}
)
MANDI_COORDS = (
    json.loads((ROOT / "backend" / "data" / "mandi_coordinates.json").read_text())
    if (ROOT / "backend" / "data" / "mandi_coordinates.json").exists()
    else {}
)

print(f"✅ Tools loaded: {len(DISEASE_DB)} diseases, {len(MANDI_COORDS)} mandis")


class tool:
    def __init__(self, func):
        self.func = func
        self.name = func.__name__
        self.__doc__ = func.__doc__

    def run(self, arg: str) -> str:
        return self.func(arg)

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)


@tool
def get_weather(location: str) -> str:
    """Get current weather and disease risk for a farm location."""
    try:
        key = os.getenv("OPENWEATHER_API_KEY")
        res = requests.get(
            "http://api.openweathermap.org/data/2.5/weather",
            params={"q": location, "appid": key, "units": "metric"},
            timeout=5,
        ).json()
        temp = res["main"]["temp"]
        humidity = res["main"]["humidity"]
        desc = res["weather"][0]["description"]
        if humidity > 80 and 20 <= temp <= 30:
            risk = "HIGH fungal risk — avoid spraying today"
        elif humidity > 60:
            risk = "MEDIUM risk — monitor closely"
        else:
            risk = "LOW risk — good conditions for spraying"
        return (
            f"Weather in {location}:\n"
            f"Temperature : {temp}°C\n"
            f"Humidity    : {humidity}%\n"
            f"Condition   : {desc}\n"
            f"Disease Risk: {risk}"
        )
    except Exception as e:
        return f"Could not fetch weather for {location}"


@tool
def get_mandi_price(crop: str) -> str:
    """Get live mandi prices for a crop."""
    fallback = {
        "tomato": {"min": 800, "max": 1500, "modal": 1200},
        "potato": {"min": 600, "max": 1200, "modal": 900},
        "onion": {"min": 1000, "max": 2000, "modal": 1500},
        "wheat": {"min": 2000, "max": 2500, "modal": 2200},
        "rice": {"min": 1800, "max": 2800, "modal": 2200},
        "cotton": {"min": 5500, "max": 6500, "modal": 6000},
    }
    try:
        key = os.getenv("AGMARKNET_API_KEY")
        if key:
            res = requests.get(
                "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070",
                params={
                    "api-key": key,
                    "format": "json",
                    "limit": 5,
                    "filters[Commodity]": crop.capitalize(),
                },
                timeout=5,
            ).json()
            if res.get("records"):
                result = f"Live Mandi Prices for {crop}:\n"
                for r in res["records"][:3]:
                    result += (
                        f"Market: {r.get('Market', 'N/A')}, {r.get('State', 'N/A')}\n"
                        f"Min: Rs.{r.get('Min Price', 'N/A')} | "
                        f"Max: Rs.{r.get('Max Price', 'N/A')} | "
                        f"Modal: Rs.{r.get('Modal Price', 'N/A')}\n---\n"
                    )
                return result
    except:
        pass
    crop_lower = crop.lower()
    if crop_lower in fallback:
        p = fallback[crop_lower]
        return (
            f"Mandi Prices for {crop}:\n"
            f"Min: Rs.{p['min']}/quintal\n"
            f"Max: Rs.{p['max']}/quintal\n"
            f"Modal: Rs.{p['modal']}/quintal\n"
            f"Note: Check local mandi for exact rates"
        )
    return f"Price data not available for {crop}"


@tool
def get_treatment(disease: str) -> str:
    """Get detailed treatment for a crop disease."""
    disease_lower = disease.lower()
    match = None

    # Try multiple matching strategies
    for key, val in DISEASE_DB.items():
        key_lower = key.lower()
        # Strategy 1 — exact contains
        if disease_lower in key_lower or key_lower in disease_lower:
            match = val
            break
        # Strategy 2 — word by word match
        disease_words = set(disease_lower.split())
        key_words = set(key_lower.split())
        if len(disease_words & key_words) >= 2:
            match = val
            break

    if match:
        remedies = match.get("remedies", {})
        organic = remedies.get("organic", [])[:3]
        chemical = remedies.get("chemical", [])[:2]
        urgency = match.get("urgency", "")
        result = f"Treatment for {match.get('display_name', disease)}:\n\n"
        if organic:
            result += "Organic:\n"
            for r in organic:
                result += f"  • {r}\n"
        if chemical:
            result += "\nChemical:\n"
            for r in chemical:
                result += f"  • {r}\n"
        result += f"\nUrgency: {urgency}"
        return result

    return (
        f"No specific treatment found. Consult local agriculture officer for {disease}"
    )


@tool
def get_disease_progression(disease: str) -> str:
    """Get how fast a disease spreads if left untreated."""
    disease_lower = disease.lower()
    for key, val in PROGRESSION_DB.items():
        if disease_lower in key.lower() or key.lower() in disease_lower:
            rate = val.get("daily_spread_rate", 0)
            note = val.get("untreated_note", "")
            day7 = min(100, rate * 7 * 100)
            return (
                f"Disease Spread Prediction:\n"
                f"Daily spread rate: {rate * 100:.0f}%\n"
                f"If untreated for 7 days: {day7:.0f}% of crop affected\n"
                f"Warning: {note}"
            )
    return f"Spread data not available for {disease}"


@tool
def get_nearby_mandis(location: str) -> str:
    """Find nearest mandis to farmer's location using coordinates."""
    location_lower = location.lower()
    found = []

    # Search by city name
    for mandi, coords in MANDI_COORDS.items():
        if (
            location_lower in mandi.lower()
            or location_lower in coords.get("state", "").lower()
        ):
            found.append(
                {
                    "name": mandi,
                    "state": coords["state"],
                    "lat": coords["lat"],
                    "lng": coords["lng"],
                }
            )

    if found:
        result = f"Mandis near {location}:\n"
        for m in found[:5]:
            result += f"  • {m['name']} ({m['state']})\n"
        return result

    # Try geocoding with OpenStreetMap (free!)
    try:
        res = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": f"{location}, India",
                "format": "json",
                "limit": 1,
                "countrycodes": "in",
            },
            headers={"User-Agent": "KrishiMitra/1.0"},
            timeout=5,
        ).json()

        if res:
            lat = float(res[0]["lat"])
            lng = float(res[0]["lon"])
            name = res[0]["display_name"].split(",")[0]
            return (
                f"Location found: {name}\n"
                f"Coordinates: {lat:.4f}, {lng:.4f}\n"
                f"Check local mandi for price details."
            )
    except:
        pass

    return f"Could not find mandis near {location}. Try a city or district name."


@tool
def get_govt_schemes(state: str) -> str:
    """Get government schemes available for farmers."""
    schemes = [
        {
            "name": "PM Fasal Bima Yojana",
            "benefit": "Crop insurance against losses",
            "how": "Visit nearest bank or CSC center",
        },
        {
            "name": "PM Kisan Samman Nidhi",
            "benefit": "Rs.6000/year direct to bank",
            "how": "Register at pmkisan.gov.in",
        },
        {
            "name": "Kisan Credit Card",
            "benefit": "Low interest crop loans",
            "how": "Apply at any nationalized bank",
        },
        {
            "name": "Soil Health Card",
            "benefit": "Free soil testing + recommendations",
            "how": "Contact local agriculture office",
        },
    ]
    result = f"Government schemes for farmers in {state}:\n\n"
    for s in schemes:
        result += (
            f"Scheme : {s['name']}\nBenefit: {s['benefit']}\nHow    : {s['how']}\n---\n"
        )
    return result
