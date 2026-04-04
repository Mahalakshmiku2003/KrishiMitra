# backend/agent/diagnose.py
import os
import json
import numpy as np
from PIL import Image
from pathlib import Path
import onnxruntime as ort

# Paths to data files
ROOT = Path(__file__).parent.parent.parent
DISEASE_DB_PATH = ROOT / "backend" / "data" / "disease_db.json"
PROG_DB_PATH = ROOT / "backend" / "data" / "progression_db.json"

# Load databases
DISEASE_DB = json.loads(DISEASE_DB_PATH.read_text()) if DISEASE_DB_PATH.exists() else {}
PROGRESSION_DB = json.loads(PROG_DB_PATH.read_text()) if PROG_DB_PATH.exists() else {}

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


def _model_crop_prefixes() -> set[str]:
    return {n.split("___")[0] for n in CLASS_NAMES if "___" in n}


def resolve_plantvillage_prefix(farmer_text: str) -> str | None:
    """
    Map farmer language / spelling to PlantVillage class prefix (e.g. Tomato).
    Returns None if crop is not supported by the classifier.
    """
    t = (farmer_text or "").strip().lower()
    if not t:
        return None
    known = _model_crop_prefixes()
    rules = [
        (("tomato", "tamatar", "టమాట"), "Tomato"),
        (("potato", "aloo", "alu", "आलू"), "Potato"),
        (("corn", "maize", "makka", "makki"), "Corn"),
        (("pepper", "mirchi", "capsicum", "bell pepper"), "Pepper"),
        (("grape", "angoor"), "Grape"),
        (("cherry",), "Cherry"),
        (("apple", "seb"), "Apple"),
        (("peach",), "Peach"),
        (("strawberry",), "Strawberry"),
        (("squash",), "Squash"),
        (("soybean", "soya"), "Soybean"),
        (("blueberry",), "Blueberry"),
        (("orange", "santara"), "Orange"),
    ]
    for keys, prefix in rules:
        if prefix not in known:
            continue
        for k in keys:
            if t == k or (len(k) >= 3 and k in t):
                return prefix
    for prefix in sorted(known, key=len, reverse=True):
        if prefix.lower() in t or t == prefix.lower():
            return prefix
    return None


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


def _severity_numeric(level: str, bbox_pct: float, conf: float) -> int:
    """
    Map diagnosis to 1–10 for detections.severity.
    Mild is capped at 5 so only Moderate+ can exceed the outbreak threshold (>5).
    """
    base = {"Mild": 3, "Moderate": 6, "Severe": 9}.get(level, 5)
    bump = int(min(2, bbox_pct / 20))
    score = min(10, base + bump)
    if level == "Mild":
        score = min(5, score)
    if conf > 0.92 and level == "Severe":
        score = min(10, score + 1)
    return max(1, score)


def _disease_spreads(raw_name: str, db_key: str) -> bool:
    """True if this is not a healthy plant and progression DB says it spreads."""
    if "healthy" in raw_name.lower():
        return False
    if not db_key or db_key not in PROGRESSION_DB:
        return False
    return PROGRESSION_DB[db_key].get("daily_spread_rate", 0) > 0


def _diagnosis_from_class(
    image_path: str,
    raw_name: str,
    conf: float,
    detector_path: str | None,
) -> dict:
    parts = raw_name.split("___")
    crop = parts[0].replace("_", " ")
    disease = parts[1].replace("_", " ") if len(parts) > 1 else "Unknown"

    db_key = CLASSIFIER_TO_DB.get(raw_name, "")
    db_entry = DISEASE_DB.get(db_key, {})
    remedies = db_entry.get("remedies", {})
    urgency = db_entry.get("urgency", "")
    pathogen = db_entry.get("pathogen", "")
    symptoms = db_entry.get("symptoms", "")

    bbox_pct = conf * 40
    severity = get_severity(bbox_pct, conf, db_entry)
    boxes = 0

    if detector_path and os.path.exists(detector_path):
        det = load_model(detector_path)
        if det:
            det_arr = preprocess(image_path, 640)
            det_out = det.run(None, {det.get_inputs()[0].name: det_arr})
            if det_out and len(det_out[0]) > 0:
                boxes = len(det_out[0])

    progression = get_progression(raw_name, bbox_pct)
    severity_level = severity.get("level", "Moderate")
    severity_score = _severity_numeric(severity_level, bbox_pct, conf)
    spreads = _disease_spreads(raw_name, db_key)

    return {
        "disease": f"{crop} {disease}",
        "pathology": disease,
        "raw_name": raw_name,
        "crop": crop,
        "confidence": f"{conf:.1%}",
        "confidence_num": conf,
        "severity": severity,
        "severity_score": severity_score,
        "spread": spreads,
        "boxes_found": boxes,
        "urgency": urgency,
        "pathogen": pathogen,
        "symptoms": symptoms,
        "remedies": remedies,
        "progression": progression,
        "error": False,
    }


def diagnose_image_for_stated_crop(
    image_path: str,
    classifier_path: str,
    detector_path: str | None,
    stated_crop_text: str,
) -> dict:
    """
    Classify disease only among PlantVillage classes for the farmer-stated crop.
    """
    try:
        prefix = resolve_plantvillage_prefix(stated_crop_text)
        if not prefix:
            return {
                "disease": "Crop not supported by disease model",
                "pathology": None,
                "confidence": "0%",
                "error": True,
            }

        allowed = [
            i
            for i, n in enumerate(CLASS_NAMES)
            if n.startswith(prefix + "___")
        ]
        if not allowed:
            return {
                "disease": f"No disease classes loaded for {prefix}",
                "pathology": None,
                "confidence": "0%",
                "error": True,
            }

        clf = load_model(classifier_path)
        if clf is None:
            return {
                "disease": "Model not found",
                "pathology": None,
                "confidence": "0%",
                "error": True,
            }

        arr = preprocess(image_path, 224)
        out = clf.run(None, {clf.get_inputs()[0].name: arr})
        probs = out[0][0]
        sub = np.array([probs[i] for i in allowed], dtype=np.float64)
        sub = sub / (sub.sum() + 1e-12)
        top_local = int(np.argmax(sub))
        conf = float(sub[top_local])
        top = allowed[top_local]
        raw_name = CLASS_NAMES[top]

        return _diagnosis_from_class(image_path, raw_name, conf, detector_path)

    except Exception as e:
        print(f"❌ Diagnosis error: {e}")
        return {
            "disease": "Could not analyze",
            "pathology": None,
            "confidence": "0%",
            "error": True,
        }


def diagnose_image(
    image_path: str, classifier_path: str, detector_path: str = None
) -> dict:
    """Unconstrained: best class over all crops (legacy / non-WhatsApp)."""
    try:
        clf = load_model(classifier_path)
        if clf is None:
            return {
                "disease": "Model not found",
                "pathology": None,
                "confidence": "0%",
                "error": True,
            }

        arr = preprocess(image_path, 224)
        out = clf.run(None, {clf.get_inputs()[0].name: arr})
        probs = out[0][0]
        top = int(np.argmax(probs))
        conf = float(probs[top])
        raw_name = CLASS_NAMES[top] if top < len(CLASS_NAMES) else "Unknown"

        return _diagnosis_from_class(image_path, raw_name, conf, detector_path)

    except Exception as e:
        print(f"❌ Diagnosis error: {e}")
        return {
            "disease": "Could not analyze",
            "pathology": None,
            "confidence": "0%",
            "error": True,
        }
