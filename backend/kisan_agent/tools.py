
from langchain.tools import tool
from services.db import SessionLocal


def _get_db():
    return SessionLocal()


@tool
def detect_disease_regions(image_path: str) -> str:
    """
    Detect diseased leaf regions in a crop photo using the YOLO model.
    Use this FIRST whenever a farmer sends any image of their plant or leaf.
    Input: local file path of the saved image (e.g. /tmp/kisan_abc123.jpg).
    Returns: yolo_label, confidence, bbox coordinates, bbox_pct, and image dimensions.
    After this, call calculate_severity with the bbox values.
    Note: yolo_label will be 'leaf' — it marks the region but does not name the disease.
    """
    try:
        from PIL import Image
        from services.yolo_service import get_model

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

        return (
            f"status: detected | "
            f"yolo_label: {top['yolo_label']} | "
            f"confidence: {top['confidence']} | "
            f"bbox_pct: {top['bbox_pct']} | "
            f"bbox: {top['bbox']} | "
            f"img_w: {top['img_w']} | img_h: {top['img_h']} | "
            f"all_detections: {detections}"
        )

    except FileNotFoundError:
        return (
            "status: model_missing | "
            "YOLO model not loaded. "
            "Ask farmer to describe symptoms — diagnosis from text also works."
        )
    except Exception as e:
        return f"status: error | {str(e)} | Ask farmer to resend a clearer photo."


@tool
def calculate_severity(
    x1: int, y1: int, x2: int, y2: int,
    img_w: int, img_h: int,
    confidence: float,
) -> str:
    """
    Calculate disease severity (Mild / Moderate / Severe) from the YOLO bounding box.
    Use this right after detect_disease_regions using the bbox values it returned.
    Input: bbox coordinates x1, y1, x2, y2 (integers),
           img_w and img_h (image dimensions from detection),
           confidence (float 0.0-1.0 from detection).
    Returns: severity level, % of image affected, and urgency description.
    """
    try:
        from services.severity_service import calculate_severity as _calc
        result = _calc(
            bbox=[x1, y1, x2, y2],
            img_w=img_w,
            img_h=img_h,
            confidence=confidence,
        )
        return (
            f"severity: {result['level']} | "
            f"affected: {result['bbox_pct']}% | "
            f"confidence: {result['confidence_pct']}% | "
            f"description: {result['description']}"
        )
    except Exception as e:
        return f"Could not calculate severity: {e}"

@tool
def lookup_disease_info(crop: str, symptoms: str, location: str = "India") -> str:
    """
    Look up disease from knowledge base using crop name and symptoms.
    Call this after farmer tells you which crop and what symptoms they see.
    Input: crop (e.g. 'Tomato'), symptoms (e.g. 'brown spots', 'yellow leaves'),
           location (farmer's state).
    Returns: disease name, remedies, urgency, prevention tips.
    """
    try:
        from services.disease_service import lookup_static, lookup_claude

        # Try constructing key the way your disease_db.json is structured
        # Pattern: "Tomato Early blight leaf", "Tomato Late blight leaf" etc.
        candidates = [
            f"{crop} {symptoms} leaf",
            f"{crop} {symptoms}",
            f"{symptoms} {crop}",
            symptoms,
        ]

        result = None
        for candidate in candidates:
            result = lookup_static(candidate)
            if result:
                print(f"[Tools] Found in DB with key: '{candidate}'")
                break

        # AI fallback if nothing found in local DB
        if not result:
            result = lookup_claude(f"{crop} {symptoms}", location)

        remedies = result.get("remedies", {})
        return (
            f"disease: {result.get('display_name', symptoms)} | "
            f"crop: {result.get('crop', crop)} | "
            f"symptoms: {result.get('symptoms', '')} | "
            f"urgency: {result.get('urgency', '')} | "
            f"organic: {remedies.get('organic', [])} | "
            f"chemical: {remedies.get('chemical', [])} | "
            f"prevention: {remedies.get('prevention', [])} | "
            f"regional_note: {result.get('regional_note', '')}"
        )
    except Exception as e:
        return f"Could not look up disease info: {e}"


@tool
def predict_disease_progression(disease_name: str, bbox_pct: float) -> str:
    """
    Predict how disease will spread over 7 days if untreated.
    Use this after lookup_disease_info to show farmer how urgent treatment is.
    Input: disease_name (same name used in lookup_disease_info, NOT 'leaf'),
           bbox_pct (affected area % from detect_disease_regions).
    Returns: day-by-day spread forecast, day-7 severity, urgency summary.
    """
    try:
        from services.progression_service import predict_progression
        result = predict_progression(disease_name, bbox_pct)
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


@tool
def get_mandi_price(commodity: str, state: str) -> str:
    """
    Get latest mandi prices for a crop in a given state.
    Use when farmer asks about price, rate, bhav, or when to sell their crop.
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
    Returns: current price, 7-day forecast, trend direction, and selling advice.
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
    Use when farmer asks where to sell, nearest mandi, or best market to go to.
    Input: location (village/city/district name), commodity (crop name),
           radius_km (optional, default 300km).
    Returns: top 5 mandis with distance, transport cost, net price per quintal.
    """
    try:
        from services.geocode_service import geocode_location
        from services.market_service import find_nearby_mandis as _find

        coords = geocode_location(location)
        if not coords:
            return f"Could not find location '{location}'. Try a nearby city name."

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
                f"net after transport: ₹{r['net_price']}/quintal\n"
            )
        return summary
    except Exception as e:
        return f"Could not find nearby markets: {e}"


ALL_TOOLS = [
    detect_disease_regions,
    calculate_severity,
    lookup_disease_info,
    predict_disease_progression,
    get_mandi_price,
    predict_price_trend,
    find_nearby_mandis,
]