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

api_key = os.getenv("GROQ_API_KEY") or "MISSING_KEY"
client = AsyncGroq(api_key=api_key)

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
You are "KrishiMitra Expert," a senior agricultural scientist and supportive companion for Indian farmers. Your goal is to provide precise, actionable, and scientific advice in English to improve crop yield and health.

### CORE KNOWLEDGE & CAPABILITIES:
- **Diseases**: When a diagnosis is provided, identify the exact disease, severity, and specify real medicines (fungicides/pesticides) with correct dosages (e.g., "2ml per liter of water").
- **Weather**: Advise on whether it's safe to spray pesticides or irrigate based on the forecast.
- **Mandi Prices**: Provide the latest rates and recommend the best market for maximum profit.
- **English Only**: You MUST respond in English at all times, even if the user asks a question in another language.

### RESPONSE GUIDELINES:
1. **Be Structured**: Use bullet points for steps and bold text for medicine or crop names.
2. **Be Practical**: Give advice that a local farmer can actually follow.
3. **Be Concise**: Avoid long paragraphs; farmers are busy!
4. **No Tool Names**: Never mention tool functions. Just present the facts.
5. **Professional Tone**: Be respectful, expert-level, and encouraging.

### DIAGNOSIS PROTOCOL (if photo results are present):
- **Headline**: State the disease name clearly in English.
- **Treatment**: List Organic and Chemical options separately.
- **Urgency**: Indicate how many days they have before significant crop loss happens.

Always end with: "Is there anything else I can help you with? 🌾"
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

        # Check for API Key
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key or api_key == "YOUR_GROQ_API_KEY":
            print("⚠️ WARNING: GROQ_API_KEY missing. Using Mock response.")
            return "Namaste! I'm in demo mode because my AI brain (API Key) isn't connected yet. But I can tell you that your crop looks interesting! 🌾"

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
