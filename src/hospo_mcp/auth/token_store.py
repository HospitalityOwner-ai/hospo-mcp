"""Token store — simple JSON file-per-venue storage for OAuth tokens.

Each venue gets its own file at tokens/{venue_id}.json.
The store handles reads, writes, and expiry-aware token retrieval.
Can be swapped for a DB-backed store later without touching callers.
"""

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import httpx
import structlog

logger = structlog.get_logger()

# Resolve token directory relative to CWD (or override via env).
TOKEN_DIR = Path(os.getenv("HOSPO_TOKEN_DIR", "tokens"))


def _token_path(venue_id: str) -> Path:
    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    # Sanitise venue_id to prevent path traversal
    safe_id = "".join(c for c in venue_id if c.isalnum() or c in ("-", "_"))
    return TOKEN_DIR / f"{safe_id}.json"


# ---------------------------------------------------------------------------
# Read / Write
# ---------------------------------------------------------------------------

def load_tokens(venue_id: str) -> Optional[dict]:
    """Load stored tokens for a venue. Returns None if not found."""
    path = _token_path(venue_id)
    if not path.exists():
        return None
    try:
        with path.open() as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("token_store.load_error", venue_id=venue_id, error=str(e))
        return None


def save_tokens(venue_id: str, data: dict) -> None:
    """Persist token data for a venue."""
    path = _token_path(venue_id)
    with path.open("w") as f:
        json.dump(data, f, indent=2)
    logger.info("token_store.saved", venue_id=venue_id)


def delete_tokens(venue_id: str) -> bool:
    """Remove stored tokens for a venue. Returns True if deleted."""
    path = _token_path(venue_id)
    if path.exists():
        path.unlink()
        logger.info("token_store.deleted", venue_id=venue_id)
        return True
    return False


def is_connected(venue_id: str) -> bool:
    """Return True if this venue has stored tokens."""
    tokens = load_tokens(venue_id)
    return tokens is not None and bool(tokens.get("access_token"))


def token_expired(tokens: dict) -> bool:
    """Return True if the access token has expired (or will in <60s)."""
    expires_at = tokens.get("expires_at")
    if not expires_at:
        return False  # No expiry info — assume still valid
    return time.time() > (expires_at - 60)


# ---------------------------------------------------------------------------
# Token exchange helpers
# ---------------------------------------------------------------------------

TOKEN_URL = "https://api.kounta.com/v1/token.json"


async def exchange_code_for_tokens(
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> dict:
    """Exchange an auth code for access + refresh tokens."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            TOKEN_URL,
            json={
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "code": code,
                "grant_type": "authorization_code",
            },
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        return resp.json()


async def refresh_access_token(
    refresh_token: str,
    client_id: str,
    client_secret: str,
) -> dict:
    """Use the refresh token to get a new access token."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            TOKEN_URL,
            json={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        return resp.json()


def build_token_record(raw: dict) -> dict:
    """Normalise a raw token response into our storage schema."""
    expires_in = raw.get("expires_in", 7200)
    return {
        "access_token": raw.get("access_token", ""),
        "refresh_token": raw.get("refresh_token", ""),
        "expires_at": time.time() + int(expires_in),
        "site_id": raw.get("site_id", raw.get("company_id", "")),
        "company_name": raw.get("company_name", raw.get("company", {}).get("name", "")),
    }


# ---------------------------------------------------------------------------
# Auto-refresh — call this before making API requests
# ---------------------------------------------------------------------------

async def get_valid_access_token(
    venue_id: str,
    client_id: str,
    client_secret: str,
) -> Optional[str]:
    """Return a valid access token for a venue, auto-refreshing if needed.

    Returns None if no tokens are stored or refresh fails.
    """
    tokens = load_tokens(venue_id)
    if not tokens or not tokens.get("access_token"):
        return None

    if token_expired(tokens) and tokens.get("refresh_token"):
        logger.info("token_store.refreshing", venue_id=venue_id)
        try:
            raw = await refresh_access_token(
                tokens["refresh_token"], client_id, client_secret
            )
            updated = build_token_record(raw)
            # Preserve fields that aren't in the refresh response
            for key in ("site_id", "company_name"):
                if not updated.get(key):
                    updated[key] = tokens.get(key, "")
            save_tokens(venue_id, updated)
            return updated["access_token"]
        except Exception as e:
            logger.error("token_store.refresh_failed", venue_id=venue_id, error=str(e))
            return None

    return tokens["access_token"]
