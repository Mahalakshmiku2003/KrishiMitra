import os
import httpx

API_KEY = os.getenv("OPENWEATHER_API_KEY")


async def get_weather(lat: float, lng: float) -> str:
    url = "https://api.openweathermap.org/data/2.5/weather"

    params = {
        "lat": lat,
        "lon": lng,
        "appid": API_KEY,
        "units": "metric",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, params=params)
            data = response.json()

        temp = data["main"]["temp"]
        humidity = data["main"]["humidity"]
        condition = data["weather"][0]["description"]

        return f"Temperature: {temp}°C, Humidity: {humidity}%, Condition: {condition}"

    except Exception as e:
        return f"Weather fetch error: {str(e)}"
