import json, os, re
from pathlib import Path
from groq import Groq

_DB_PATH = Path(__file__).parent.parent / "data" / "disease_db.json"
with open(_DB_PATH) as f:
    DISEASE_DB = json.load(f)

_client = None

def _get_client():
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise EnvironmentError("GROQ_API_KEY not set in .env")
        _client = Groq(api_key=api_key)
    return _client

def lookup_static(disease_name: str) -> dict | None:
    if disease_name in DISEASE_DB:
        return DISEASE_DB[disease_name]
    dn_lower = disease_name.lower().strip()
    for key, val in DISEASE_DB.items():
        if key.lower().strip() == dn_lower:
            return val
    return None

def lookup_claude(disease_name: str, location: str = "India") -> dict:
    client = _get_client()
    prompt = f"""
A plant disease classifier identified the disease as: "{disease_name}"
Farmer location: {location}

Return ONLY valid JSON, no markdown, no explanation:
{{
  "display_name": "human readable name",
  "crop": "crop name",
  "pathogen": "causal organism and type",
  "symptoms": "2-3 sentence description of visible symptoms",
  "spread": "how and under what conditions this disease spreads",
  "remedies": {{
    "organic": ["remedy 1", "remedy 2", "remedy 3"],
    "chemical": ["remedy with dosage 1", "remedy with dosage 2"],
    "prevention": ["tip 1", "tip 2", "tip 3"]
  }},
  "urgency": "one sentence on how urgently farmer must act",
  "regional_note": "India-specific advice on products or seasonal risk"
}}
"""
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=900,
    )
    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    parsed = json.loads(raw)
    parsed.setdefault("remedies", {})
    parsed["remedies"].setdefault("organic", [])
    parsed["remedies"].setdefault("chemical", [])
    parsed["remedies"].setdefault("prevention", [])
    parsed.setdefault("regional_note", "")
    return parsed