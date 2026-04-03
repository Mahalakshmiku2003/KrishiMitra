import os, random
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from backend.services.market_service import get_price_history, get_all_latest_prices

SEASONAL_TRENDS = {
    "Tomato":  [1.2, 1.1, 0.9, 0.8, 0.9, 1.1, 1.3, 1.2, 1.0, 0.9, 0.8, 1.0],
    "Onion":   [0.9, 0.8, 0.8, 0.9, 1.0, 1.2, 1.3, 1.2, 1.1, 1.0, 0.9, 0.9],
    "Potato":  [1.0, 1.0, 0.9, 0.9, 1.0, 1.1, 1.1, 1.0, 1.0, 1.0, 1.0, 1.0],
    "default": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
}


def predict_prices(commodity: str, market: str, db: Session, days_ahead: int = 7) -> dict:
    """
    Predict prices using stored historical data if available,
    falls back to seasonal model with today's live price.
    """
    history = get_price_history(commodity, market, db)

    if len(history) >= 7:
        # Enough data — use weighted moving average trend
        prices        = [r["modal_price"] for r in history]
        current_price = prices[-1]
        avg_change    = (prices[-1] - prices[0]) / len(prices)
        model_used    = "historical_trend"
    else:
        # Not enough history yet — use latest price from DB or API
        from backend.services.market_service import get_all_latest_prices
        all_prices = get_all_latest_prices(commodity, db)
        if all_prices:
            modal_prices  = [p["modal_price"] for p in all_prices]
            current_price = round(sum(modal_prices) / len(modal_prices), 2)
        else:
            return {
                "commodity": commodity,
                "market":    market,
                "error":     f"No price data found for {commodity}. Run /market/fetch first.",
                "model":     "none",
            }
        avg_change = 0
        model_used = "seasonal_trend"

    trend_key     = commodity.title() if commodity.title() in SEASONAL_TRENDS else "default"
    monthly_trend = SEASONAL_TRENDS[trend_key]
    current_month = datetime.now().month

    predictions = []
    price       = current_price

    for i in range(1, days_ahead + 1):
        future_date    = datetime.now() + timedelta(days=i)
        future_month   = future_date.month
        seasonal_factor = monthly_trend[future_month - 1] / monthly_trend[current_month - 1]

        random.seed(i * 42)
        daily_noise = 1 + random.uniform(-0.02, 0.02)
        trend_delta = avg_change * 0.5  # dampened trend
        predicted   = round((price + trend_delta) * seasonal_factor * daily_noise, 2)
        predicted   = max(predicted, 0)
        price       = predicted

        predictions.append({
            "date":            future_date.strftime("%Y-%m-%d"),
            "predicted_price": predicted,
        })

    day7_price = predictions[-1]["predicted_price"]
    change_pct = round(((day7_price - current_price) / current_price) * 100, 1)

    if change_pct > 5:
        trend  = "rising"
        advice = f"Prices expected to rise {change_pct}% — consider holding stock for better returns."
    elif change_pct < -5:
        trend  = "falling"
        advice = f"Prices expected to fall {abs(change_pct)}% — consider selling now."
    else:
        trend  = "stable"
        advice = "Prices expected to remain stable. Sell at your convenience."

    return {
        "commodity":         commodity,
        "market":            market,
        "current_price":     current_price,
        "day_7_price":       day7_price,
        "change_pct":        change_pct,
        "trend":             trend,
        "advice":            advice,
        "daily_predictions": predictions,
        "data_points_used":  len(history),
        "model":             model_used,
    }