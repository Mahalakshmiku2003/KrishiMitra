import os
from pathlib import Path
from ultralytics import YOLO

MODEL_PATH = os.getenv("YOLO_MODEL_PATH", "best.pt")
_model = None


def get_model() -> YOLO:
    global _model
    if _model is None:
        if not Path(MODEL_PATH).exists():
            raise FileNotFoundError(
                f"Model not found at '{MODEL_PATH}'. "
                "Set YOLO_MODEL_PATH in your .env or place best.pt in the project root."
            )
        _model = YOLO(MODEL_PATH)
    return _model
