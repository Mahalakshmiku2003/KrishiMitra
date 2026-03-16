from pydantic import BaseModel
from typing import List, Optional

class BBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float

class Detection(BaseModel):
    disease:    str
    confidence: float
    severity:   str
    bbox:       BBox

class DiagnosisResponse(BaseModel):
    status:     str
    detections: List[Detection]