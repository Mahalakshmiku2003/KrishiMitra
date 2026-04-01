# backend/agent/agent.py
import os
from groq import AsyncGroq
from dotenv import load_dotenv
from agent.tools import (
    get_weather,
    get_mandi_price,
    get_treatment,
    get_govt_schemes,
    get_disease_progression,
    get_nearby_mandis,
)

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
# Fallback to backend/.env when running from project root.
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

memory_store = {}


def get_history(farmer_id: str) -> list:
    if farmer_id not in memory_store:
        memory_store[farmer_id] = []
    return memory_store[farmer_id]


def save_message(farmer_id: str, role: str, content: str):
    history = get_history(farmer_id)
    history.append({"role": role, "content": content})
    if len(history) > 10:
        memory_store[farmer_id] = history[-10:]


SYSTEM_PROMPT = """
You are KrishiMitra, a friendly AI farming assistant for Indian farmers.

IMPORTANT: Never mention tool names like get_treatment or get_nearby_mandis
in your reply. Just use the data they return naturally in your response.

When farmer sends crop photo with diagnosis:
1. Tell disease name and severity clearly
2. Give specific treatment with medicine names and dosage
3. Warn how fast it spreads if untreated
4. Give urgency level

When farmer asks about prices:
1. Give current rates
2. Suggest nearest mandi to sell

When farmer asks about schemes:
1. List schemes with how to apply

Rules:
- Always reply in SAME language as farmer
- Hindi → Hindi reply
- English → English reply  
- Keep replies SHORT and PRACTICAL
- Never mention tool names in reply
-format the replays in clean way
- Always end with: 'Koi aur madad chahiye? 🌾'
"""


async def process_message(
    farmer_id: str, message: str, disease_result: dict = None
) -> str:
    try:
        # Build context from disease result
        if disease_result and not disease_result.get("error"):
            disease = disease_result.get("disease", "")
            conf = disease_result.get("confidence", "")
            severity = disease_result.get("severity", {})
            urgency = disease_result.get("urgency", "")
            prog = disease_result.get("progression", {})

            context = (
                f"CROP PHOTO ANALYSIS RESULT:\n"
                f"Disease   : {disease}\n"
                f"Confidence: {conf}\n"
                f"Severity  : {severity.get('level', 'Unknown')} — {severity.get('description', '')}\n"
                f"Urgency   : {urgency}\n"
            )
            if prog:
                context += (
                    f"If untreated: {prog.get('day_7_spread', '?')} crop affected in 7 days\n"
                    f"Warning: {prog.get('warning', '')}\n"
                )
            message = f"{context}\nFarmer message: {message or 'Please help me'}"

        history = get_history(farmer_id)
        messages = (
            [{"role": "system", "content": SYSTEM_PROMPT}]
            + history
            + [{"role": "user", "content": message}]
        )

        # Check if tools needed
        tool_result = await use_tools(message, disease_result)
        if tool_result:
            messages.append(
                {"role": "user", "content": f"Additional data:\n{tool_result}"}
            )

        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.3,
            max_tokens=600,
        )

        reply = response.choices[0].message.content
        save_message(farmer_id, "user", message)
        save_message(farmer_id, "assistant", reply)
        return reply

    except Exception as e:
        return f"Sorry, please try again. Error: {str(e)}"


async def use_tools(message: str, disease_result: dict = None) -> str:
    msg_lower = message.lower()
    results = []

    # Auto-use treatment tool if disease detected
    if disease_result and not disease_result.get("error"):
        disease = disease_result.get("disease", "")
        if disease and disease != "Could not analyze":
            results.append(get_treatment.run(disease))
            results.append(get_disease_progression.run(disease))

    # Weather tool
    if any(
        w in msg_lower
        for w in ["weather", "rain", "spray", "mausam", "barish", "humid"]
    ):
        location = extract_location(message)
        results.append(get_weather.run(location))

    # Price tool
    if any(
        w in msg_lower for w in ["price", "rate", "mandi", "bhav", "sell", "market"]
    ):
        crop = extract_crop(message)
        results.append(get_mandi_price.run(crop))

    # Nearby mandis
    if any(w in msg_lower for w in ["nearby", "nearest", "closest", "paas", "kahan"]):
        location = extract_location(message)
        results.append(get_nearby_mandis.run(location))

    # Schemes
    if any(
        w in msg_lower for w in ["scheme", "subsidy", "insurance", "yojana", "sarkar"]
    ):
        results.append(get_govt_schemes.run("India"))

    return "\n\n".join(results) if results else ""


def extract_location(message: str) -> str:
    cities = [
        "pune",
        "mumbai",
        "delhi",
        "bangalore",
        "bengaluru",
        "hyderabad",
        "nashik",
        "nagpur",
        "chennai",
        "kolkata",
        "ahmedabad",
        "jaipur",
        "lucknow",
        "patna",
        "bhopal",
        "indore",
        "chandigarh",
        "ludhiana",
        "amritsar",
        "kochi",
    ]
    msg_lower = message.lower()
    for city in cities:
        if city in msg_lower:
            return city.capitalize()
    return "Pune"


def extract_crop(message: str) -> str:
    crops = [
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
    ]
    msg_lower = message.lower()
    for crop in crops:
        if crop in msg_lower:
            return crop
    return "tomato"
