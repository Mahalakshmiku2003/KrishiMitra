"""
Twilio WhatsApp media: GET with HTTP Basic auth, then often 302 to a signed CDN URL.
Do not forward Authorization to the CDN. Support Account SID + Auth Token or API Key + Secret.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import urljoin

import requests
from dotenv import load_dotenv

load_dotenv()
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.is_file():
    load_dotenv(_env_path)


def _strip_cred(v: str | None) -> str:
    return (v or "").strip().strip('"').strip("'")


def _http_basic_user_password() -> tuple[str, str]:
    """
    Prefer API Key (SK…) + Secret if set — same as Twilio docs for REST.
    Else Account SID (AC…) + Auth Token.
    """
    key_sid = _strip_cred(os.getenv("TWILIO_API_KEY_SID"))
    key_secret = _strip_cred(os.getenv("TWILIO_API_KEY_SECRET"))
    if key_sid.startswith("SK") and key_secret:
        return key_sid, key_secret

    sid = _strip_cred(os.getenv("TWILIO_ACCOUNT_SID"))
    token = _strip_cred(os.getenv("TWILIO_AUTH_TOKEN"))
    if not sid or not token:
        raise ValueError(
            "Set TWILIO_ACCOUNT_SID + TWILIO_AUTH_TOKEN, or TWILIO_API_KEY_SID + TWILIO_API_KEY_SECRET"
        )
    return sid, token


def _account_sid_in_media_url(media_url: str) -> str | None:
    m = re.search(r"/Accounts/(AC[a-f0-9]+)/", media_url, re.I)
    return m.group(1) if m else None


def download_twilio_media_sync(media_url: str) -> bytes:
    if not media_url or not media_url.startswith("http"):
        raise ValueError("Invalid Twilio media URL")

    user, password = _http_basic_user_password()
    env_ac = _strip_cred(os.getenv("TWILIO_ACCOUNT_SID"))
    url_ac = _account_sid_in_media_url(media_url)
    if url_ac and env_ac and url_ac != env_ac:
        # Subaccount media URL with parent credentials often yields 401
        print(
            f"[TwilioMedia] WARN: URL Account {url_ac[:6]}… != TWILIO_ACCOUNT_SID {env_ac[:6]}… "
            "— use that subaccount’s Auth Token (or API key for that account)."
        )

    headers = {
        "Accept": "*/*",
        "User-Agent": "KrishiMitra-TwilioMedia/1.0",
    }

    r = requests.get(
        media_url,
        auth=(user, password),
        timeout=45,
        allow_redirects=False,
        headers=headers,
    )

    if r.status_code == 200 and r.content:
        return r.content

    if r.status_code in (301, 302, 303, 307, 308):
        loc = r.headers.get("location")
        if not loc:
            r.raise_for_status()
        next_url = urljoin(media_url, loc)
        # Signed URL: no Basic auth, minimal headers (some CDNs reject Authorization)
        r2 = requests.get(next_url, timeout=60, allow_redirects=True)
        if r2.status_code == 401:
            raise PermissionError(
                "CDN returned 401 after Twilio redirect — try again; if it persists, check Twilio media URL freshness."
            )
        r2.raise_for_status()
        return r2.content

    if r.status_code == 401:
        raise PermissionError(
            "Twilio returned 401 Unauthorized when fetching media. "
            "Use the Auth Token (or API Key Secret) for the *same* Twilio account as in the media URL "
            "(for subaccounts, use the subaccount SID + subaccount token). "
            "Optional: set TWILIO_API_KEY_SID + TWILIO_API_KEY_SECRET instead of the primary token."
        )

    r.raise_for_status()
    return r.content
