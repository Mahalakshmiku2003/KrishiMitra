"""Pending crop-disease photo: user sends image first, then crop name in a follow-up message."""

from __future__ import annotations

import os
import time

from farmer_store import normalize_phone

_pending: dict[str, dict] = {}
TTL_SEC = 86400


def set_pending_crop_image(phone: str, image_path: str) -> None:
    """Store path to the latest disease photo; replaces any older pending file."""
    pid = normalize_phone(phone)
    old = _pending.get(pid)
    if old and old.get("path"):
        op = old["path"]
        if op != image_path and os.path.isfile(op):
            try:
                os.remove(op)
            except OSError:
                pass
    _pending[pid] = {"path": image_path, "ts": time.time()}


def peek_pending_crop_image(phone: str) -> str | None:
    """Return pending image path if valid and not expired."""
    pid = normalize_phone(phone)
    rec = _pending.get(pid)
    if not rec:
        return None
    if time.time() - rec["ts"] > TTL_SEC:
        clear_pending_crop_image(phone)
        return None
    p = rec.get("path")
    if not p or not os.path.isfile(p):
        _pending.pop(pid, None)
        return None
    return p


def take_pending_crop_image(phone: str) -> str | None:
    """Remove pending state and return path (caller deletes file after use)."""
    pid = normalize_phone(phone)
    rec = _pending.pop(pid, None)
    if not rec:
        return None
    return rec.get("path")


def clear_pending_crop_image(phone: str) -> None:
    pid = normalize_phone(phone)
    rec = _pending.pop(pid, None)
    if rec and rec.get("path") and os.path.isfile(rec["path"]):
        try:
            os.remove(rec["path"])
        except OSError:
            pass
