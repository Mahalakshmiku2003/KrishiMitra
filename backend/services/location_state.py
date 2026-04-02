# services/location_state.py
# Shared state — no imports from agent or whatsapp_service, so no circular dependency.

_pending_location: dict = {}