import re
import time
import os
import sys
from datetime import datetime, timezone

UTC = timezone.utc
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from sqlalchemy.dialects.postgresql import insert

# Ensure imports work when running as:
#   python scripts/scrape_karnataka_napanta.py
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from backend.models.price import MandiPrice
from backend.services.db import SessionLocal

BASE_URL = "https://www.napanta.com"
SEED_URLS = [
    "https://www.napanta.com/market-price/karnataka/bangalore/bangalore",
    "https://www.napanta.com/market-price/karnataka/bellary/bellary",
    "https://www.napanta.com/market-price/karnataka/koppal/kustagi",
]

HEADERS = {"User-Agent": "Mozilla/5.0"}

MAX_PAGES = 50
REQUEST_DELAY = 1.0


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def safe_float_from_rupee(text: str) -> float:
    cleaned = re.sub(r"[^\d.]", "", text.replace(",", ""))
    return float(cleaned) if cleaned else 0.0


def parse_arrival_date(text: str):
    text = normalize_space(text)
    for fmt in ("%d %b %Y", "%d %B %Y", "%d-%b-%Y", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return datetime.now(UTC).date()


def extract_district_from_url(url: str) -> str:
    path = urlparse(url).path.strip("/").split("/")
    if len(path) >= 4:
        return path[2].replace("-", " ").title()
    return "Unknown"


def is_price_token(text: str) -> bool:
    return bool(re.match(r"^₹\s*[\d,]+$", normalize_space(text)))


def is_date_token(text: str) -> bool:
    return bool(re.match(r"^\d{1,2}\s+[A-Za-z]{3,}\s+\d{4}$", normalize_space(text)))


def is_text_token(text: str) -> bool:
    text = normalize_space(text)
    if not text:
        return False
    if is_price_token(text):
        return False
    if is_date_token(text):
        return False

    lower = text.lower()

    blocked_contains = [
        "for free price alerts",
        "price trend",
        "commodity amc market variety maximum price average price minimum price last updated on",
        "other wholesale mandi market prices",
        "seed dealers",
        "fertilizer dealers",
        "cold storages",
        "pesticide dealers",
        "browse all categories",
        "best agriculture platform in india",
        "daily market prices",
        "mobile app",
        "copyright",
    ]

    if any(x in lower for x in blocked_contains):
        return False

    if text.startswith("#"):
        return False

    return True


def clean_tokens(lines):
    tokens = []
    for line in lines:
        line = normalize_space(line)
        if not line:
            continue

        lower = line.lower()

        # remove obvious noise
        if line.startswith("#"):
            continue
        if "for free price alerts" in lower:
            continue
        if "price trend" in lower:
            continue
        if (
            "commodity amc market variety maximum price average price minimum price last updated on"
            in lower
        ):
            continue
        if "browse all categories" in lower:
            continue
        if "best agriculture platform in india" in lower:
            continue
        if "daily market prices" in lower:
            continue
        if "mobile app" in lower:
            continue

        tokens.append(line)

    return tokens


def parse_market_page(url: str):
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    district = extract_district_from_url(url)

    text = soup.get_text("\n", strip=True)
    lines = [
        normalize_space(line) for line in text.splitlines() if normalize_space(line)
    ]
    tokens = clean_tokens(lines)

    rows = []
    i = 0

    while i <= len(tokens) - 7:
        # actual token order from your debug output:
        # commodity, market, variety, ₹max, ₹avg, ₹min, date
        t0, t1, t2, t3, t4, t5, t6 = tokens[i : i + 7]

        if (
            is_text_token(t0)
            and is_text_token(t1)
            and is_text_token(t2)
            and is_price_token(t3)
            and is_price_token(t4)
            and is_price_token(t5)
            and is_date_token(t6)
        ):
            row = {
                "state": "Karnataka",
                "district": district,
                "market": t1,
                "commodity": t0,
                "variety": t2 or "General",
                "min_price": safe_float_from_rupee(t5),
                "max_price": safe_float_from_rupee(t3),
                "modal_price": safe_float_from_rupee(t4),
                "arrival_date": parse_arrival_date(t6),
                "fetched_at": datetime.now(UTC),
            }
            rows.append(row)
            i += 7
            continue

        i += 1

    return rows, soup


def extract_karnataka_market_links(soup: BeautifulSoup):
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        full_url = urljoin(BASE_URL, href)

        if "/market-price/karnataka/" in full_url:
            if "play.google.com" in full_url or "bit.ly" in full_url:
                continue
            links.add(full_url)

    return links


def upsert_rows(db, rows):
    inserted = 0

    for row in rows:
        stmt = (
            insert(MandiPrice)
            .values(
                state=row["state"],
                district=row["district"],
                market=row["market"],
                commodity=row["commodity"],
                variety=row["variety"],
                min_price=row["min_price"],
                max_price=row["max_price"],
                modal_price=row["modal_price"],
                arrival_date=row["arrival_date"],
                fetched_at=row["fetched_at"],
            )
            .on_conflict_do_nothing(constraint="uq_market_commodity_date")
        )

        db.execute(stmt)
        inserted += 1

    db.commit()
    return inserted


def run():
    db = SessionLocal()

    visited = set()
    queue = list(SEED_URLS)

    total_pages = 0
    total_rows = 0

    try:
        while queue and total_pages < MAX_PAGES:
            url = queue.pop(0)

            if url in visited:
                continue

            visited.add(url)
            total_pages += 1
            print(f"[{total_pages}] Scraping: {url}")

            try:
                rows, soup = parse_market_page(url)

                if rows:
                    inserted = upsert_rows(db, rows)
                    total_rows += len(rows)
                    print(f"    rows parsed: {len(rows)} | insert attempts: {inserted}")
                    print(f"    sample: {rows[:2]}")
                else:
                    print("    rows parsed: 0")

                new_links = extract_karnataka_market_links(soup)
                for link in new_links:
                    if link not in visited and link not in queue:
                        queue.append(link)

            except Exception as e:
                print(f"    failed: {e}")

            time.sleep(REQUEST_DELAY)

    finally:
        db.close()

    print(f"\nDone. Pages visited: {total_pages}")
    print(f"Total rows parsed: {total_rows}")
    print(f"Unique URLs discovered: {len(visited)}")


if __name__ == "__main__":
    run()
