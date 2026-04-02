# routes/market.py

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from services.db import get_db
from services.market_service import (
    get_latest_prices,
    get_all_latest_prices,
    find_nearby_mandis,
)
from services.prediction_service import predict_prices
from services.geocode_service import geocode_location
from services.price_fetcher import run_daily_fetch

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/prices")
async def live_prices(
    commodity: str,
    state: str = None,
    db: Session = Depends(get_db),
):
    try:
        if state:
            prices = get_latest_prices(commodity, state, db)
        else:
            prices = get_all_latest_prices(commodity, db)

        if not prices:
            return JSONResponse({
                "status": "no_data",
                "commodity": commodity,
                "message": (
                    f"No data in DB for {commodity}. "
                    f"Call POST /market/fetch first to load official data and Karnataka fallback data."
                ),
                "prices": []
            })

        modal_prices = [p["modal_price"] for p in prices]
        return JSONResponse({
            "status": "success",
            "commodity": commodity,
            "total": len(prices),
            "summary": {
                "min_price": min(modal_prices),
                "max_price": max(modal_prices),
                "avg_price": round(sum(modal_prices) / len(modal_prices), 2),
            },
            "prices": prices,
        })

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


class NearbyRequest(BaseModel):
    commodity: str
    location: str
    radius_km: float = 300
    top_n: int = 3


@router.post("/nearby")
async def nearby_mandis(
    request: NearbyRequest,
    db: Session = Depends(get_db),
):
    try:
        coords = geocode_location(request.location)
        if not coords:
            return JSONResponse(
                status_code=404,
                content={
                    "error": (
                        f"Could not find location '{request.location}'. "
                        "Try a more specific name like 'Mysore, Karnataka'."
                    )
                }
            )

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
                "status": "no_data",
                "commodity": request.commodity,
                "farmer_location": coords,
                "message": (
                    f"No mandis found within {request.radius_km}km "
                    f"for {request.commodity}. Try increasing radius_km."
                ),
                "mandis": []
            })

        best = results[0]
        return JSONResponse({
            "status": "success",
            "commodity": request.commodity,
            "farmer_location": {
                "input": request.location,
                "resolved": coords["display_name"],
                "lat": coords["lat"],
                "lng": coords["lng"],
            },
            "best_market": {
                "market": best["market"],
                "state": best["state"],
                "modal_price": best["modal_price"],
                "distance_km": best["distance_km"],
                "transport_cost": best["transport_cost"],
                "net_price": best["net_price"],
                "date": best["date"],
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


class NearbyCoordsRequest(BaseModel):
    commodity: str
    farmer_lat: float
    farmer_lng: float
    radius_km: float = 300
    top_n: int = 3


@router.post("/nearby-by-coords")
async def nearby_mandis_by_coords(
    request: NearbyCoordsRequest,
    db: Session = Depends(get_db),
):
    try:
        results = find_nearby_mandis(
            farmer_lat=request.farmer_lat,
            farmer_lng=request.farmer_lng,
            commodity=request.commodity,
            radius_km=request.radius_km,
            top_n=request.top_n,
            db=db,
        )

        if not results:
            return JSONResponse({
                "status": "no_data",
                "commodity": request.commodity,
                "message": (
                    f"No mandis found within {request.radius_km}km "
                    f"for {request.commodity}. Try increasing radius_km."
                ),
                "mandis": []
            })

        best = results[0]
        return JSONResponse({
            "status": "success",
            "commodity": request.commodity,
            "farmer_location": {
                "lat": request.farmer_lat,
                "lng": request.farmer_lng,
            },
            "best_market": {
                "market": best["market"],
                "district": best["district"],
                "state": best["state"],
                "modal_price": best["modal_price"],
                "distance_km": best["distance_km"],
                "transport_cost": best["transport_cost"],
                "net_price": best["net_price"],
                "date": best["date"],
            },
            "recommendation": (
                f"Sell in {best['market']}, {best['district']}, {best['state']} — "
                f"net ₹{best['net_price']}/quintal after "
                f"₹{best['transport_cost']} transport ({best['distance_km']}km away)."
            ),
            "top_mandis": results,
        })

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

        
@router.get("/predict")
async def price_prediction(
    commodity: str,
    market: str,
    db: Session = Depends(get_db),
):
    try:
        result = predict_prices(commodity, market, db)
        return JSONResponse({"status": "success", **result})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.post("/fetch")
async def trigger_fetch():
    """
    Loads official mandi data and fills Karnataka gaps using fallback scrape.
    """
    try:
        result = run_daily_fetch()
        return JSONResponse({
            "status": "success",
            "message": "Mandi fetch completed.",
            **result
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
