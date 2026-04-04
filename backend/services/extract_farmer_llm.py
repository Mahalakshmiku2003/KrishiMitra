"""LLM extraction for farmer profile fields (shared by WhatsApp handlers)."""

import json
import re

from groq import AsyncGroq
import os


async def extract_farmer_data(message: str) -> dict:
    client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
    try:
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": """Extract farmer info.

Return ONLY JSON:
{
  "location": "city or null",
  "crop": "crop name or null",
  "disease": "disease or null",
  "language": "Hindi/English/Kannada"
}""",
                },
                {"role": "user", "content": message},
            ],
            temperature=0.1,
        )
        raw = response.choices[0].message.content
        raw = re.sub(r"```json|```", "", raw).strip()
        return json.loads(raw)
    except Exception as e:
        print(f"⚠️ extract_farmer_data failed: {e}")
        return {}
