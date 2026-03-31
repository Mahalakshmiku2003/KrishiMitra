from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from services.progression_service import predict_progression

router = APIRouter()

class ProgressionRequest(BaseModel):
    disease_name:     str
    current_bbox_pct: float   # bbox_pct value from /detect response

@router.post("/")
async def progression(request: ProgressionRequest):
    """
    Predicts how the disease will progress over 7 days if untreated.
    Pass disease_name + current bbox_pct directly from /detect response.
    No image needed — pure calculation.

    Body:
    {
        "disease_name":     "Tomato Early blight leaf",
        "current_bbox_pct": 34.2
    }
    """
    try:
        if request.current_bbox_pct < 0 or request.current_bbox_pct > 100:
            return JSONResponse(
                status_code=422,
                content={"error": "current_bbox_pct must be between 0 and 100"}
            )

        result = predict_progression(request.disease_name, request.current_bbox_pct)

        return JSONResponse({
            "status":       "predicted",
            "disease_name": request.disease_name,
            "progression":  result,
        })

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})