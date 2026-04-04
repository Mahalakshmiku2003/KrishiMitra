# Shared onboarding flags (no imports from agent/whatsapp).

_pending_name: dict[str, bool] = {}


def mark_pending_name(phone: str) -> None:
    from farmer_store import normalize_phone

    _pending_name[normalize_phone(phone)] = True


def clear_pending_name(phone: str) -> None:
    from farmer_store import normalize_phone

    _pending_name.pop(normalize_phone(phone), None)


def is_pending_name(phone: str) -> bool:
    from farmer_store import normalize_phone

    return _pending_name.get(normalize_phone(phone), False)
