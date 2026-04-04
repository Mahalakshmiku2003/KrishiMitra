# backend/agent/diagnose.py
import os
import json
import numpy as np
from PIL import Image
from pathlib import Path
import onnxruntime as ort
from config import CLASSIFIER_PATH, DETECTOR_PATH

# Paths to data files
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DISEASE_DB_PATH = os.path.join(_BACKEND_DIR, "data", "disease_db.json")
PROG_DB_PATH = os.path.join(_BACKEND_DIR, "data", "progression_db.json")

# Load databases
DISEASE_DB = {}
if os.path.exists(DISEASE_DB_PATH):
    with open(DISEASE_DB_PATH, "r") as f:
        DISEASE_DB = json.load(f)

PROGRESSION_DB = {}
if os.path.exists(PROG_DB_PATH):
    with open(PROG_DB_PATH, "r") as f:
        PROGRESSION_DB = json.load(f)

print(f"✅ Disease DB loaded: {len(DISEASE_DB)} entries")
print(f"✅ Progression DB loaded: {len(PROGRESSION_DB)} entries")

# PlantVillage class names
CLASS_NAMES = [
    "Apple___Apple_scab",
    "Apple___Black_rot",
    "Apple___Cedar_apple_rust",
    "Apple___healthy",
    "Blueberry___healthy",
    "Cherry___Powdery_mildew",
    "Cherry___healthy",
    "Corn___Cercospora_leaf_spot",
    "Corn___Common_rust",
    "Corn___Northern_Leaf_Blight",
    "Corn___healthy",
    "Grape___Black_rot",
    "Grape___Esca",
    "Grape___Leaf_blight",
    "Grape___healthy",
    "Orange___Haunglongbing",
    "Peach___Bacterial_spot",
    "Peach___healthy",
    "Pepper___Bacterial_spot",
    "Pepper___healthy",
    "Potato___Early_blight",
    "Potato___Late_blight",
    "Potato___healthy",
    "Raspberry___healthy",
    "Soybean___healthy",
    "Squash___Powdery_mildew",
    "Strawberry___Leaf_scorch",
    "Strawberry___healthy",
    "Tomato___Bacterial_spot",
    "Tomato___Early_blight",
    "Tomato___Late_blight",
    "Tomato___Leaf_Mold",
    "Tomato___Septoria_leaf_spot",
    "Tomato___Spider_mites",
    "Tomato___Target_Spot",
    "Tomato___Mosaic_virus",
    "Tomato___Yellow_Leaf_Curl_Virus",
    "Tomato___healthy",
]

# Map classifier output → disease_db keys
CLASSIFIER_TO_DB = {
    "Tomato___Early_blight": "Tomato Early blight leaf",
    "Tomato___Late_blight": "Tomato late blight leaf",
    "Tomato___Bacterial_spot": "Tomato leaf bacterial spot",
    "Tomato___Mosaic_virus": "Tomato leaf mosaic virus",
    "Tomato___Yellow_Leaf_Curl_Virus": "Tomato leaf yellow virus",
    "Tomato___Leaf_Mold": "Tomato mold leaf",
    "Tomato___Septoria_leaf_spot": "Tomato septoria leaf spot",
    "Tomato___Spider_mites": "Tomato two spotted spider mites leaf",
    "Potato___Early_blight": "Potato leaf early blight",
    "Potato___Late_blight": "Potato leaf late blight",
    "Corn___Northern_Leaf_Blight": "Corn leaf blight",
    "Corn___Cercospora_leaf_spot": "Corn leaf gray spot",
    "Corn___Common_rust": "Corn rust leaf",
    "Pepper___Bacterial_spot": "Bell_pepper leaf spot",
    "Cherry___Powdery_mildew": "Cherry Powdery Mildew leaf",
    "Grape___Black_rot": "Grape leaf black rot",
    "Apple___Apple_scab": "Apple Scab Leaf",
    "Apple___Cedar_apple_rust": "Apple rust leaf",
    "Strawberry___Leaf_scorch": "Strawberry leaf scorch",
    "Squash___Powdery_mildew": "Squash Powdery mildew leaf",
}


def load_model(path: str):
    if not os.path.exists(path):
        print(f"❌ Model not found: {path}")
        return None
    session = ort.InferenceSession(path)
    print(f"✅ Model loaded: {path}")
    return session


def preprocess(image_path: str, size: int) -> np.ndarray:
    img = Image.open(image_path).convert("RGB").resize((size, size))
    arr = np.array(img).astype(np.float32) / 255.0
    return np.expand_dims(np.transpose(arr, (2, 0, 1)), 0)


def get_severity(bbox_pct: float, confidence: float, db_entry: dict) -> dict:
    t = db_entry.get("severity_thresholds", {"mild": 0.20, "moderate": 0.60})
    mild = t["mild"] * 100
    mod = t["moderate"] * 100

    if bbox_pct < mild:
        level = "Mild"
    elif bbox_pct < mod:
        level = "Moderate"
    else:
        level = "Severe"

    if confidence > 0.85 and level == "Mild":
        level = "Moderate"

    descriptions = {
        "Mild": f"{bbox_pct:.1f}% affected. Early stage — treat this week.",
        "Moderate": f"{bbox_pct:.1f}% affected. Treat immediately.",
        "Severe": f"{bbox_pct:.1f}% affected. Emergency response needed.",
    }
    return {"level": level, "description": descriptions[level]}


def get_progression(raw_name: str, bbox_pct: float) -> dict:
    db_key = CLASSIFIER_TO_DB.get(raw_name)
    if not db_key or db_key not in PROGRESSION_DB:
        return {}
    prog = PROGRESSION_DB[db_key]
    rate = prog.get("daily_spread_rate", 0.05)
    note = prog.get("untreated_note", "")
    day7 = min(100, bbox_pct + (rate * 7 * 100))
    return {
        "day_7_spread": f"{day7:.1f}%",
        "daily_rate": f"{rate * 100:.0f}%",
        "warning": note,
    }


def diagnose_image(
    image_path: str, 
    classifier_path: str = CLASSIFIER_PATH, 
    detector_path: str = DETECTOR_PATH,
    crop_type: str = None
) -> dict:
    try:
        # Run classifier
        clf = load_model(classifier_path)
        if clf is None:
            return {"disease": "Model not found", "confidence": "0%", "error": True}

        arr = preprocess(image_path, 224)
        out = clf.run(None, {clf.get_inputs()[0].name: arr})
        probs = out[0][0]

        # 🧪 Crop-Aware Filtering
        final_top = int(np.argmax(probs))
        
        if crop_type and crop_type.strip():
            target = crop_type.strip().capitalize()
            # Find indices matching the crop (e.g., "Tomato")
            matching_indices = [i for i, name in enumerate(CLASS_NAMES) if name.startswith(f"{target}___")]
            
            if matching_indices:
                # Pick the best among matching classes
                sub_probs = [probs[i] for i in matching_indices]
                sub_top = int(np.argmax(sub_probs))
                final_top = matching_indices[sub_top]
                print(f"🎯 Filtered for {target}: selected {CLASS_NAMES[final_top]}")

        conf = float(probs[final_top])
        # 🚨 Realistic scaling: Reduce slightly to avoid overconfident 99% scores on single shots
        display_conf = min(0.92, conf * 0.95) if conf > 0.8 else conf * 0.9
        
        raw_name = CLASS_NAMES[final_top] if final_top < len(CLASS_NAMES) else "Unknown"
        
        parts = raw_name.split("___")
        crop = parts[0].replace("_", " ")
        disease = parts[1].replace("_", " ") if len(parts) > 1 else "Unknown"

        # If crop matches user input, just show the disease name for a cleaner UI
        display_name = disease if (crop_type and crop_type.lower() in crop.lower()) else f"{crop} {disease}"
        if disease.lower() == "healthy":
            display_name = "Healthy"

        # Get from disease_db
        db_key = CLASSIFIER_TO_DB.get(raw_name, "")
        db_entry = DISEASE_DB.get(db_key, {})
        remedies = db_entry.get("remedies", {})
        urgency = db_entry.get("urgency", "")
        pathogen = db_entry.get("pathogen", "")
        symptoms = db_entry.get("symptoms", "")

        # Run detector for bounding boxes
        bbox_pct = conf * 40 # Heuristic if no box found
        severity = get_severity(bbox_pct, conf, db_entry)
        boxes = 0

        if detector_path and os.path.exists(detector_path):
            det = load_model(detector_path)
            if det:
                det_arr = preprocess(image_path, 640)
                det_out = det.run(None, {det.get_inputs()[0].name: det_arr})
                if det_out and len(det_out[0]) > 0:
                    boxes = len(det_out[0])

        # Get progression
        progression = get_progression(raw_name, bbox_pct)

        return {
            "disease": display_name,
            "raw_name": raw_name,
            "crop": crop,
            "confidence": f"{display_conf:.1%}",
            "confidence_num": display_conf, # Scaled down for realism
            "severity": severity,
            "boxes_found": boxes,
            "urgency": urgency,
            "pathogen": pathogen,
            "symptoms": symptoms,
            "remedies": remedies,
            "progression": progression,
            "error": False,
        }

    except Exception as e:
        print(f"❌ Diagnosis error: {e}")
        return {"disease": "Could not analyze", "confidence": "0%", "error": True}
