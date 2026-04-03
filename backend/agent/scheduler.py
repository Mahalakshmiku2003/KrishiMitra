# backend/agent/scheduler.py
"""
Compatibility shim for old imports.

All production scheduler logic now lives in backend/scheduler.py.
This file simply re-exports the public scheduler API.
"""

from backend.scheduler import (
    scheduler,
    start_scheduler,
    stop_scheduler,
    morning_briefing,
    send_morning_briefings,
    daily_karnataka_scrape,
    check_price_alerts,
    schedule_followup,
)

__all__ = [
    "scheduler",
    "start_scheduler",
    "stop_scheduler",
    "morning_briefing",
    "send_morning_briefings",
    "daily_karnataka_scrape",
    "check_price_alerts",
    "schedule_followup",
]
