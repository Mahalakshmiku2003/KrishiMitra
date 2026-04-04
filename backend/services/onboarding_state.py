"""In-memory onboarding flags (per process)."""


def _norm(phone: str) -> str:
    return (phone or "").replace("whatsapp:", "").strip()


_pending_name: set[str] = set()


def mark_pending_name(phone: str) -> None:
    _pending_name.add(_norm(phone))


def clear_pending_name(phone: str) -> None:
    _pending_name.discard(_norm(phone))


def is_pending_name(phone: str) -> bool:
    return _norm(phone) in _pending_name
