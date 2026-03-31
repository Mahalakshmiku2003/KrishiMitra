"""
kisan_agent/tools.py
Key fix: detect_disease_regions now calls calculate_severity internally.
Agent only calls one tool for photo analysis — no chance to hallucinate bbox values.
"""

from langchain.tools import tool
from services.db import SessionLocal
import json, os, tempfile

CACHE_FILE = os.path.join(tempfile.gettempdir(), "kisan_last_detection.json")


def _get_db():
    return SessionLocal()


def _save_detection_cache(bbox_pct: float, severity: str, affected_pct: float):
    """Save detection result to temp file so agent.py can persist it to DB."""
    with open(CACHE_FILE, "w") as f:
        json.dump({
            "bbox_pct":    bbox_pct,
            "severity":    severity,
            "affected_pct": affected_pct,
        }, f)
    print(f"[Tools] Detection cached: {affected_pct}% {severity}")


def read_detection_cache() -> dict:
    """Read last detection from cache. Called by agent.py after image processing."""
    try:
        with open(CACHE_FILE) as f:
            return json.load(f)
    except:
        return {"bbox_pct": 20.0, "severity": "unknown", "affected_pct": 20.0}


def _lookup_case_insensitive(query: str):
    from services.disease_service import lookup_static
    candidates = [
        query,
        query + " leaf",
        query.title(),
        query.title() + " leaf",
        query.lower(),
        query.lower() + " leaf",
        query.replace("_", " "),
        query.replace("_", " ") + " leaf",
    ]
    for candidate in candidates:
        result = lookup_static(candidate)
        if result:
            print(f"[Tools] DB match: '{candidate}'")
            return result
    return None


# ── Combined detect + severity in ONE tool ──────────────────────────────────────

@tool
def analyze_crop_image(image_path: str) -> str:
    """
    Analyze a crop photo — detects diseased regions AND calculates severity in one step.
    Use this as the ONLY tool when a farmer sends an image. Do not call any other
    detection or severity tool separately.
    Input: local file path of the saved image (e.g. C:/Users/.../kisan_abc.jpg).
    Returns: severity level, affected percentage, bbox details — everything in one result.
    After this, ask farmer which crop and what symptoms, then call lookup_disease_info.
    """
    try:
        from PIL import Image
        from services.yolo_service import get_model
        from services.severity_service import calculate_severity as _calc

        model        = get_model()
        img          = Image.open(image_path).convert("RGB")
        img_w, img_h = img.size
        results      = model(image_path, verbose=False)[0]

        if results.boxes is None or len(results.boxes) == 0:
            return (
                "status: no_detection | "
                "No diseased region found. Crop looks healthy or image is unclear. "
                "Ask farmer to send a closer photo of the affected leaf."
            )

        detections = []
        for box in results.boxes:
            x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
            conf     = float(box.conf)
            label    = model.names[int(box.cls)]
            bbox_pct = round(((x2 - x1) * (y2 - y1)) / (img_w * img_h) * 100, 1)
            detections.append({
                "yolo_label": label,
                "confidence": round(conf, 3),
                "bbox":       {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
                "bbox_pct":   bbox_pct,
                "img_w":      img_w,
                "img_h":      img_h,
            })

        detections.sort(key=lambda x: x["confidence"], reverse=True)
        top = detections[0]

        # Calculate severity using ACTUAL bbox values — no agent involvement
        severity_result = _calc(
            bbox=[
                top["bbox"]["x1"], top["bbox"]["y1"],
                top["bbox"]["x2"], top["bbox"]["y2"]
            ],
            img_w=img_w,
            img_h=img_h,
            confidence=top["confidence"],
        )

        # Save to cache so agent.py can persist to DB
        _save_detection_cache(
            bbox_pct=top["bbox_pct"],
            severity=severity_result["level"],
            affected_pct=severity_result["bbox_pct"],
        )

        return (
            f"status: detected | "
            f"severity: {severity_result['level']} | "
            f"affected_pct: {severity_result['bbox_pct']}% | "
            f"confidence: {severity_result['confidence_pct']}% | "
            f"description: {severity_result['description']} | "
            f"bbox_pct: {top['bbox_pct']} | "
            f"yolo_label: {top['yolo_label']}"
        )

    except FileNotFoundError:
        return (
            "status: model_missing | "
            "YOLO model not loaded. "
            "Ask farmer to describe symptoms — diagnosis from text also works."
        )
    except Exception as e:
        return f"status: error | {str(e)} | Ask farmer to resend a clearer photo."


"""
Replace the lookup_disease_info tool in kisan_agent/tools.py with this version.
Also replace the _lookup_case_insensitive helper.
"""

# ── Remove _lookup_case_insensitive entirely — replaced by semantic search ──────

@tool
def lookup_disease_info(crop: str, symptoms: str, location: str = "India") -> str:
    """
    Look up disease from knowledge base using crop name and symptoms.
    Call this after farmer tells you which crop and what symptoms they see.
    Input: crop (e.g. 'Tomato', 'Potato'), symptoms (e.g. 'Late Blight', 'brown spots'),
           location (farmer's state).
    Returns: disease name, ALL remedies with dosage, urgency, prevention tips.
    """
    try:
        from services.disease_search import semantic_search
        from services.disease_service import lookup_claude

        # Build search query from crop + symptoms
        query  = f"{crop} {symptoms}".strip()
        result = semantic_search(query, threshold=0.35)

        # AI fallback only if semantic search finds nothing above threshold
        if not result:
            print(f"[Tools] Semantic search no match, using AI fallback for: {query}")
            result = lookup_claude(query, location)

        remedies = result.get("remedies", {})
        return (
            f"disease: {result.get('display_name', symptoms)} | "
            f"crop: {result.get('crop', crop)} | "
            f"pathogen: {result.get('pathogen', '')} | "
            f"symptoms: {result.get('symptoms', '')} | "
            f"spread: {result.get('spread', '')} | "
            f"urgency: {result.get('urgency', '')} | "
            f"organic: {remedies.get('organic', [])} | "
            f"chemical: {remedies.get('chemical', [])} | "
            f"prevention: {remedies.get('prevention', [])} | "
            f"regional_note: {result.get('regional_note', '')}"
        )
    except Exception as e:
        return f"Could not look up disease info: {e}"


# ── Progression ─────────────────────────────────────────────────────────────────

@tool
def predict_disease_progression(disease_name: str, bbox_pct: float) -> str:
    """
    Predict how disease will spread over 7 days if untreated.
    Use this after lookup_disease_info.
    Input: disease_name (e.g. 'Tomato late blight leaf'),
           bbox_pct (use affected_pct value from analyze_crop_image result,
                     or last_bbox_pct from farmer profile for text messages).
    Returns: day-by-day spread, day-7 forecast, urgency summary.
    """
    try:
        from services.progression_service import predict_progression
        result = predict_progression(disease_name, min(bbox_pct, 50.0))
        return (
            f"current: {result['current_infected_pct']}% | "
            f"day_7: {result['day_7_infected_pct']}% | "
            f"increase: {result['relative_increase_pct']}% worse if untreated | "
            f"spread_type: {result['spread_type']} | "
            f"summary: {result['summary']} | "
            f"warning: {result['untreated_note']}"
        )
    except Exception as e:
        return f"Could not predict progression: {e}"


# ── Market tools ────────────────────────────────────────────────────────────────

@tool
def get_mandi_price(commodity: str, state: str) -> str:
    """
    Get latest mandi prices for a crop in a given state.
    Use when farmer asks about price, rate, bhav, or when to sell.
    Input: commodity (e.g. 'Tomato', 'Onion', 'Wheat') and
           state (e.g. 'Karnataka', 'Maharashtra', 'Punjab').
    Returns: min, max, modal price per quintal across markets in that state.
    """
    try:
        from services.market_service import get_latest_prices
        db      = _get_db()
        results = get_latest_prices(commodity, state, db)
        db.close()

        if not results:
            return f"No price data found for {commodity} in {state}."

        summary = f"Latest {commodity} prices in {state}:\n"
        for r in results[:5]:
            summary += (
                f"  {r['market']}: modal ₹{r['modal_price']}/quintal "
                f"(min ₹{r['min_price']}, max ₹{r['max_price']}) — {r['date']}\n"
            )
        return summary
    except Exception as e:
        return f"Could not fetch mandi price: {e}"


@tool
def predict_price_trend(commodity: str, market: str) -> str:
    """
    Predict whether crop prices will rise or fall over the next 7 days.
    Use when farmer asks 'should I sell now or wait?' or about price trends.
    Input: commodity (e.g. 'Tomato') and market name (e.g. 'Bangalore').
    Returns: current price, 7-day forecast, trend direction, selling advice.
    """
    try:
        from services.prediction_service import predict_prices
        db     = _get_db()
        result = predict_prices(commodity, market, db, days_ahead=7)
        db.close()

        if "error" in result:
            return result["error"]

        return (
            f"{commodity} at {market}: ₹{result['current_price']}/quintal now | "
            f"7-day forecast: ₹{result['day_7_price']} "
            f"({result['change_pct']}% — {result['trend']}) | "
            f"Advice: {result['advice']}"
        )
    except Exception as e:
        return f"Could not predict price trend: {e}"


@tool
def find_nearby_mandis(location: str, commodity: str, radius_km: float = 300.0) -> str:
    """
    Find best nearby mandis ranked by net price after transport cost.
    Use when farmer asks where to sell, nearest mandi, or best market.
    Input: location (village/city/district), commodity (crop name),
           radius_km (optional, default 300km).
    Returns: top 5 mandis with distance, transport cost, net price per quintal.
    """
    try:
        from services.geocode_service import geocode_location
        from services.market_service import find_nearby_mandis as _find

        coords = geocode_location(location)
        if not coords:
            return f"Could not find '{location}'. Try a nearby city name."

        db      = _get_db()
        results = _find(
            farmer_lat=coords["lat"],
            farmer_lng=coords["lng"],
            commodity=commodity,
            radius_km=radius_km,
            top_n=5,
            db=db,
        )
        db.close()

        if not results:
            return f"No {commodity} markets found within {radius_km}km of {location}."

        summary = f"Best {commodity} markets near {location}:\n"
        for r in results:
            summary += (
                f"  {r['market']}, {r['state']} | "
                f"₹{r['modal_price']}/quintal | "
                f"{r['distance_km']}km away | "
                f"net: ₹{r['net_price']}/quintal\n"
            )
        return summary
    except Exception as e:
        return f"Could not find nearby markets: {e}"


ALL_TOOLS = [
    analyze_crop_image,        # replaces detect_disease_regions + calculate_severity
    lookup_disease_info,
    predict_disease_progression,
    get_mandi_price,
    predict_price_trend,
    find_nearby_mandis,
]