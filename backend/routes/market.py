from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from services.db import get_db
from services.market_service import (
    get_latest_prices, get_all_latest_prices, find_nearby_mandis
)
from services.prediction_service import predict_prices
from services.geocode_service import geocode_location
from services.price_fetcher import run_daily_fetch

router = APIRouter()


# =============================================================================
# GET /market/prices
# Latest stored prices for a commodity — optionally filter by state
# =============================================================================

@router.get("/prices")
async def live_prices(
    commodity: str,
    state:     str = None,
    db:        Session = Depends(get_db),
):
    """
    Returns latest available mandi prices for a commodity from DB.
    Shows most recent data per market even if not updated today.
    Run /market/fetch first to populate the DB.
    """
    try:
        if state:
            prices = get_latest_prices(commodity, state, db)
        else:
            prices = get_all_latest_prices(commodity, db)

        if not prices:
            return JSONResponse({
                "status":    "no_data",
                "commodity": commodity,
                "message":   f"No data in DB for {commodity}. Call POST /market/fetch first.",
                "prices":    []
            })

        modal_prices = [p["modal_price"] for p in prices]
        return JSONResponse({
            "status":    "success",
            "commodity": commodity,
            "total":     len(prices),
            "summary": {
                "min_price": min(modal_prices),
                "max_price": max(modal_prices),
                "avg_price": round(sum(modal_prices) / len(modal_prices), 2),
            },
            "prices": prices,
        })

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# =============================================================================
# POST /market/nearby
# Best mandis near farmer — farmer types location name
# =============================================================================

class NearbyRequest(BaseModel):
    commodity: str
    location:  str          # farmer types "Nashik" or "Warangal district"
    radius_km: float = 300
    top_n:     int   = 3

@router.post("/nearby")
async def nearby_mandis(
    request: NearbyRequest,
    db:      Session = Depends(get_db),
):
    """
    Farmer types their village/district/city name.
    Geocodes it to lat/lng, then finds nearest mandis with best net price.

    Body:
    {
        "commodity": "Tomato",
        "location":  "Nashik",
        "radius_km": 300,
        "top_n":     3
    }
    """
    try:
        # Step 1 — geocode farmer location
        coords = geocode_location(request.location)
        if not coords:
            return JSONResponse(
                status_code=404,
                content={
                    "error": f"Could not find location '{request.location}'. "
                             "Try a more specific name like 'Nashik, Maharashtra'."
                }
            )

        # Step 2 — find nearby mandis from DB
        results = find_nearby_mandis(
            farmer_lat=coords["lat"],
            farmer_lng=coords["lng"],
            commodity=request.commodity,
            radius_km=request.radius_km,
            top_n=request.top_n,
            db=db,
        )

        if not results:
            return JSONResponse({
                "status":           "no_data",
                "commodity":        request.commodity,
                "farmer_location":  coords,
                "message":          f"No mandis found within {request.radius_km}km "
                                    f"for {request.commodity}. Try increasing radius_km.",
                "mandis":           []
            })

        best = results[0]
        return JSONResponse({
            "status":    "success",
            "commodity": request.commodity,
            "farmer_location": {
                "input":        request.location,
                "resolved":     coords["display_name"],
                "lat":          coords["lat"],
                "lng":          coords["lng"],
            },
            "best_market": {
                "market":         best["market"],
                "state":          best["state"],
                "modal_price":    best["modal_price"],
                "distance_km":    best["distance_km"],
                "transport_cost": best["transport_cost"],
                "net_price":      best["net_price"],
                "date":           best["date"],
            },
            "recommendation": (
                f"Sell in {best['market']}, {best['state']} — "
                f"net ₹{best['net_price']}/quintal after "
                f"₹{best['transport_cost']} transport ({best['distance_km']}km away)."
            ),
            "top_mandis": results,
        })

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# =============================================================================
# GET /market/predict
# 7-day price prediction using stored historical data
# =============================================================================

@router.get("/predict")
async def price_prediction(
    commodity: str,
    market:    str,
    db:        Session = Depends(get_db),
):
    """
    Predict commodity prices for the next 7 days.
    Uses stored historical data if available, seasonal model as fallback.
    """
    try:
        result = predict_prices(commodity, market, db)
        return JSONResponse({"status": "success", **result})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# =============================================================================
# POST /market/fetch
# Manually trigger the daily price fetch — also called by cron job
# =============================================================================

@router.post("/fetch")
async def trigger_fetch():
    """
    Fetches today's prices for all commodities from data.gov.in
    and stores them in PostgreSQL.

    Call this once now to populate the DB.
    After that the cron job runs it automatically every midnight.
    """
    try:
        total = run_daily_fetch()
        return JSONResponse({
            "status":  "success",
            "message": f"Fetched and stored {total} price records.",
            "total":   total,
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})