import json
from pathlib import Path

_PROG_PATH = Path(__file__).parent.parent / "data" / "progression_db.json"
with open(_PROG_PATH) as f:
    PROGRESSION_DB = json.load(f)

def predict_progression(disease_name: str, current_bbox_pct: float) -> dict:
    """
    Predicts 7-day disease spread using per-disease daily spread rate.

    current_bbox_pct : infected area % from YOLO bbox (0-100)
    daily_spread_rate: how much the infected % grows per day if untreated
    """
    entry = PROGRESSION_DB.get(disease_name)

    # Fuzzy match if exact not found
    if not entry:
        dn_lower = disease_name.lower().strip()
        for key, val in PROGRESSION_DB.items():
            if key.lower().strip() == dn_lower:
                entry = val
                break

    # Default rates if disease not in progression DB
    if not entry:
        entry = {
            "daily_spread_rate": 0.06,
            "max_spread":        0.85,
            "spread_type":       "unknown",
            "untreated_note":    "Monitor closely and treat immediately."
        }

    daily_rate = entry["daily_spread_rate"]   # e.g. 0.08 = 8% per day
    max_spread = entry["max_spread"] * 100    # convert to %
    current    = current_bbox_pct

    # Project day by day
    daily_projections = []
    pct = current

    for day in range(1, 8):
        # Logistic-style growth — slows as it approaches max
        remaining  = max_spread - pct
        growth     = daily_rate * remaining
        pct        = min(pct + growth, max_spread)
        pct        = round(pct, 1)

        if pct < 20:
            severity = "Mild"
        elif pct < 60:
            severity = "Moderate"
        else:
            severity = "Severe"

        daily_projections.append({
            "day":           day,
            "infected_pct":  pct,
            "severity":      severity,
        })

    final_pct    = daily_projections[-1]["infected_pct"]
    increase_pct = round(final_pct - current_bbox_pct, 1)
    increase_rel = round((increase_pct / current_bbox_pct) * 100) if current_bbox_pct > 0 else 0

    # Human-readable summary like "This will worsen 40% if untreated"
    summary = f"This will worsen by {increase_rel}% if untreated — infected area grows from {current_bbox_pct}% to {final_pct}% over 7 days."

    return {
        "current_infected_pct":  current_bbox_pct,
        "day_7_infected_pct":    final_pct,
        "absolute_increase_pct": increase_pct,
        "relative_increase_pct": increase_rel,
        "spread_type":           entry["spread_type"],
        "summary":               summary,
        "untreated_note":        entry["untreated_note"],
        "daily_projections":     daily_projections,
    }