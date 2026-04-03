import os, base64, json, re
from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse
from groq import Groq
from backend.services.file_service import save_upload, cleanup

router = APIRouter()

SYMPTOM_REFERENCE = """
Nitrogen (N) deficiency    : Yellowing starts on older/lower leaves, moves upward. Pale green overall.
Phosphorus (P) deficiency  : Purple or reddish tint on leaf undersides and stems. Dark green older leaves.
Potassium (K) deficiency   : Brown scorching on leaf edges and tips (marginal scorch). Older leaves first.
Iron (Fe) deficiency       : Yellowing between veins on young/new leaves. Veins stay green (interveinal chlorosis).
Magnesium (Mg) deficiency  : Yellowing between veins on older leaves. Veins stay green. Leaves may curl.
Calcium (Ca) deficiency    : Distorted, curled young leaves. Brown leaf tips. Blossom end rot on fruit.
Sulfur (S) deficiency      : Uniform yellowing of young leaves. Similar to N but starts at top not bottom.
Zinc (Zn) deficiency       : Small leaves, shortened internodes, mottled yellowing on young leaves.
Manganese (Mn) deficiency  : Interveinal chlorosis on young leaves, similar to Fe but less intense.
Boron (B) deficiency       : Thick, brittle, distorted young leaves. Growing tip may die.
"""

@router.post("/")
async def soil_deficiency(
    file:     UploadFile = File(...),
    crop:     str        = Form(default="unknown"),
    location: str        = Form(default="India"),
):
    """
    Pass a plant image → Llama Vision analyses visual symptoms
    → identifies likely soil / nutrient deficiencies.
    """
    tmp_path = save_upload(file)
    try:
        with open(tmp_path, "rb") as f:
            image_data   = f.read()
            image_base64 = base64.standard_b64encode(image_data).decode("utf-8")

        filename = file.filename.lower()
        if filename.endswith(".png"):
            media_type = "image/png"
        elif filename.endswith(".webp"):
            media_type = "image/webp"
        else:
            media_type = "image/jpeg"

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise EnvironmentError("GROQ_API_KEY not set in .env")

        client = Groq(api_key=api_key)

        prompt = f"""
You are an expert agronomist analysing a plant image for soil and nutrient deficiencies.
Crop: {crop}
Farmer location: {location}

Use this symptom reference to guide your analysis:
{SYMPTOM_REFERENCE}

Look carefully at the image. Identify any visible symptoms of nutrient deficiency.

Return ONLY valid JSON, no markdown, no explanation:
{{
  "deficiencies_detected": true or false,
  "identified": [
    {{
      "nutrient":      "Nitrogen",
      "symbol":        "N",
      "confidence":    "High / Medium / Low",
      "symptoms_seen": "what you can see in the image that indicates this",
      "remedy": {{
        "organic":  "organic treatment with dosage",
        "chemical": "chemical treatment with dosage",
        "timing":   "when to apply"
      }}
    }}
  ],
  "overall_soil_health": "Good / Fair / Poor",
  "summary": "2-3 sentence overall assessment",
  "recommendation": "most urgent action the farmer should take"
}}

If no deficiency symptoms are visible, return deficiencies_detected as false and identified as empty array.
"""
        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type};base64,{image_base64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }],
            max_tokens=1000,
        )

        raw = response.choices[0].message.content.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        result = json.loads(raw)

        return JSONResponse({
            "status": "analysed",
            "crop":   crop,
            "result": result,
        })

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        cleanup(tmp_path)
