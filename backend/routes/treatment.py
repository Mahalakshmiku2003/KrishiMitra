from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse
from backend.services.disease_service import lookup_static, lookup_claude

router = APIRouter()

@router.post("/")
async def treatment(
    disease_name: str  = Form(...),
    location:     str  = Form(default="India"),
    force_ai:     bool = Form(default=False),
):
    """
    Step 2.
    Pass disease name from your friend's classifier
    → returns full treatment info, remedies, urgency.
    Checks static disease_db.json first, falls back to Claude API.
    """
    try:
        entry  = None
        source = None

        if not force_ai:
            entry = lookup_static(disease_name)
            if entry:
                source = "static_db"

        if entry is None:
            entry  = lookup_claude(disease_name, location)
            source = "claude_api"

        return JSONResponse({
            "status":        "found",
            "source":        source,
            "disease_name":  disease_name,
            "display_name":  entry.get("display_name", disease_name),
            "crop":          entry.get("crop", "Unknown"),
            "pathogen":      entry.get("pathogen", "Unknown"),
            "symptoms":      entry.get("symptoms", ""),
            "spread":        entry.get("spread", ""),
            "remedies":      entry.get("remedies", {
                "organic": [], "chemical": [], "prevention": []
            }),
            "urgency":       entry.get("urgency", ""),
            "regional_note": entry.get("regional_note", ""),
        })

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})