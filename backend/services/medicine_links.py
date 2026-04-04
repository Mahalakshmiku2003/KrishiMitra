"""Build search links for buying agri inputs online (generic, no affiliate)."""

from __future__ import annotations

from urllib.parse import quote_plus


def remedy_buy_links(remedies: dict | None, max_links: int = 3) -> list[str]:
    if not remedies:
        return []
    out: list[str] = []
    for key in ("chemical", "organic"):
        for line in remedies.get(key, [])[:2]:
            phrase = (line or "").split(",")[0].strip()[:90]
            if len(phrase) < 4:
                continue
            q = quote_plus(f"{phrase} buy agricultural India fungicide insecticide")
            out.append(f"https://www.google.com/search?q={q}")
            if len(out) >= max_links:
                return out
    return out
