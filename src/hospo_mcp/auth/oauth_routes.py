"""OAuth 2.0 routes for Lightspeed O-Series (Kounta) onboarding.

Exposes four endpoints that handle the full OAuth lifecycle:
  GET  /auth/lightspeed            — redirect to Lightspeed auth page
  GET  /auth/lightspeed/callback   — receive code, exchange for tokens
  GET  /auth/status                — check connection status
  POST /auth/disconnect            — remove stored tokens
  GET  /connect                    — HTML connect page for venue operators
"""

import os
import uuid
from typing import Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from .token_store import (
    build_token_record,
    delete_tokens,
    exchange_code_for_tokens,
    is_connected,
    load_tokens,
    save_tokens,
)
import structlog

logger = structlog.get_logger()

LIGHTSPEED_AUTH_URL = "https://api.kounta.com/v1/oauth/authorize"
DEFAULT_VENUE_ID = "default"  # Single-venue deployments use this key


def get_oauth_config() -> dict:
    """Pull OAuth credentials from environment."""
    return {
        "client_id": os.getenv("LIGHTSPEED_CLIENT_ID", ""),
        "client_secret": os.getenv("LIGHTSPEED_CLIENT_SECRET", ""),
        "redirect_uri": os.getenv(
            "LIGHTSPEED_REDIRECT_URI",
            "http://localhost:8000/auth/lightspeed/callback",
        ),
    }


def oauth_configured(cfg: dict) -> bool:
    return bool(cfg["client_id"] and cfg["client_secret"])


def register_oauth_routes(app: FastAPI) -> None:
    """Attach OAuth routes to an existing FastAPI app."""

    # ── /auth/lightspeed ──────────────────────────────────────────────────────

    @app.get("/auth/lightspeed", tags=["auth"])
    async def auth_lightspeed(venue_id: str = DEFAULT_VENUE_ID):
        """Redirect the operator's browser to the Lightspeed OAuth consent page."""
        cfg = get_oauth_config()
        if not oauth_configured(cfg):
            raise HTTPException(
                status_code=501,
                detail=(
                    "OAuth not configured. Set LIGHTSPEED_CLIENT_ID, "
                    "LIGHTSPEED_CLIENT_SECRET, and LIGHTSPEED_REDIRECT_URI."
                ),
            )

        state = str(uuid.uuid4())
        # Embed venue_id in state so the callback knows which file to write.
        # Format: "{uuid}:{venue_id}"
        compound_state = f"{state}:{venue_id}"

        params = (
            f"response_type=code"
            f"&client_id={cfg['client_id']}"
            f"&redirect_uri={cfg['redirect_uri']}"
            f"&state={compound_state}"
        )
        url = f"{LIGHTSPEED_AUTH_URL}?{params}"
        logger.info("auth.redirect", venue_id=venue_id, state=state)
        return RedirectResponse(url=url, status_code=302)

    # ── /auth/lightspeed/callback ─────────────────────────────────────────────

    @app.get("/auth/lightspeed/callback", tags=["auth"])
    async def auth_lightspeed_callback(
        code: Optional[str] = None,
        state: Optional[str] = None,
        error: Optional[str] = None,
        error_description: Optional[str] = None,
    ):
        """Receive auth code from Lightspeed, exchange for tokens, store them."""
        if error:
            logger.warning("auth.callback_error", error=error, description=error_description)
            return HTMLResponse(
                content=_error_page(error, error_description),
                status_code=400,
            )

        if not code:
            raise HTTPException(status_code=400, detail="Missing 'code' parameter.")

        # Extract venue_id from compound state
        venue_id = DEFAULT_VENUE_ID
        if state and ":" in state:
            _, venue_id = state.split(":", 1)

        cfg = get_oauth_config()
        if not oauth_configured(cfg):
            raise HTTPException(status_code=501, detail="OAuth not configured.")

        try:
            raw = await exchange_code_for_tokens(
                code=code,
                client_id=cfg["client_id"],
                client_secret=cfg["client_secret"],
                redirect_uri=cfg["redirect_uri"],
            )
        except Exception as e:
            logger.error("auth.token_exchange_failed", error=str(e))
            raise HTTPException(
                status_code=502,
                detail=f"Token exchange failed: {str(e)}",
            )

        record = build_token_record(raw)
        save_tokens(venue_id, record)
        logger.info("auth.connected", venue_id=venue_id, company=record.get("company_name"))

        return HTMLResponse(content=_success_page(record, venue_id))

    # ── /auth/status ──────────────────────────────────────────────────────────

    @app.get("/auth/status", tags=["auth"])
    async def auth_status(venue_id: str = DEFAULT_VENUE_ID):
        """Return connection status for a venue."""
        connected = is_connected(venue_id)
        if connected:
            tokens = load_tokens(venue_id)
            return {
                "status": "connected",
                "venue_id": venue_id,
                "company_name": tokens.get("company_name", ""),
                "site_id": tokens.get("site_id", ""),
            }
        return {"status": "disconnected", "venue_id": venue_id}

    # ── /auth/disconnect ──────────────────────────────────────────────────────

    @app.post("/auth/disconnect", tags=["auth"])
    async def auth_disconnect(venue_id: str = DEFAULT_VENUE_ID):
        """Remove stored tokens for a venue (disconnect Lightspeed)."""
        deleted = delete_tokens(venue_id)
        logger.info("auth.disconnected", venue_id=venue_id, had_tokens=deleted)
        return {"status": "disconnected", "venue_id": venue_id}

    # ── /connect ──────────────────────────────────────────────────────────────

    @app.get("/connect", response_class=HTMLResponse, tags=["auth"])
    async def connect_page(venue_id: str = DEFAULT_VENUE_ID):
        """HTML connect page — venue operator lands here to link Lightspeed."""
        cfg = get_oauth_config()
        connected = is_connected(venue_id)
        tokens = load_tokens(venue_id) if connected else None
        return HTMLResponse(content=_connect_page(venue_id, connected, tokens, oauth_configured(cfg)))


# ---------------------------------------------------------------------------
# HTML templates
# ---------------------------------------------------------------------------

def _connect_page(venue_id: str, connected: bool, tokens: Optional[dict], oauth_ready: bool) -> str:
    if connected and tokens:
        company = tokens.get("company_name") or "Your venue"
        site_id = tokens.get("site_id") or "—"
        status_block = f"""
        <div class="status connected">
          <div class="status-icon">✓</div>
          <div>
            <strong>{company}</strong> is connected to hospo-mcp.<br>
            <small>Site ID: {site_id}</small>
          </div>
        </div>
        <form method="post" action="/auth/disconnect?venue_id={venue_id}"
              onsubmit="return confirm('Disconnect Lightspeed? This will remove stored tokens.');">
          <button type="submit" class="btn btn-danger">Disconnect</button>
        </form>
        """
    elif not oauth_ready:
        status_block = """
        <div class="status warning">
          <div class="status-icon">⚠</div>
          <div>
            <strong>OAuth not configured.</strong><br>
            Set <code>LIGHTSPEED_CLIENT_ID</code>, <code>LIGHTSPEED_CLIENT_SECRET</code>,
            and <code>LIGHTSPEED_REDIRECT_URI</code> to enable the connect flow.
            <br><br>
            Running in <strong>mock/demo mode</strong> — no real connection required.
          </div>
        </div>
        """
    else:
        status_block = f"""
        <div class="status disconnected">
          <div class="status-icon">○</div>
          <div>Not connected. Link your Lightspeed account to get started.</div>
        </div>
        <a href="/auth/lightspeed?venue_id={venue_id}" class="btn btn-primary">
          Connect your Lightspeed account
        </a>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>hospo-mcp — Connect Lightspeed</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #f5f5f5;
      color: #1a1a1a;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px;
    }}
    .card {{
      background: #fff;
      border-radius: 12px;
      box-shadow: 0 2px 16px rgba(0,0,0,.08);
      padding: 40px;
      max-width: 480px;
      width: 100%;
    }}
    .logo {{
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 32px;
    }}
    .logo-mark {{
      width: 36px; height: 36px;
      background: #1a1a2e;
      border-radius: 8px;
      display: flex; align-items: center; justify-content: center;
      color: #fff; font-weight: 700; font-size: 18px;
    }}
    .logo-text {{ font-size: 20px; font-weight: 700; letter-spacing: -.3px; }}
    .logo-sub {{ font-size: 12px; color: #888; margin-top: 1px; }}
    h1 {{ font-size: 22px; font-weight: 700; margin-bottom: 8px; }}
    .subtitle {{ color: #666; font-size: 15px; margin-bottom: 28px; line-height: 1.5; }}
    .status {{
      display: flex; align-items: flex-start; gap: 14px;
      padding: 16px; border-radius: 8px; margin-bottom: 20px;
      font-size: 14px; line-height: 1.6;
    }}
    .status.connected {{ background: #f0fdf4; border: 1px solid #86efac; }}
    .status.disconnected {{ background: #f8fafc; border: 1px solid #e2e8f0; }}
    .status.warning {{ background: #fffbeb; border: 1px solid #fcd34d; }}
    .status-icon {{
      font-size: 20px; flex-shrink: 0; width: 28px;
      text-align: center; margin-top: 1px;
    }}
    .status.connected .status-icon {{ color: #16a34a; }}
    .status.disconnected .status-icon {{ color: #94a3b8; }}
    .status.warning .status-icon {{ color: #d97706; }}
    .btn {{
      display: inline-block;
      padding: 12px 24px;
      border-radius: 8px;
      font-size: 15px;
      font-weight: 600;
      text-decoration: none;
      border: none; cursor: pointer;
      transition: opacity .15s;
    }}
    .btn:hover {{ opacity: .85; }}
    .btn-primary {{ background: #1a1a2e; color: #fff; }}
    .btn-danger {{ background: #fee2e2; color: #b91c1c; }}
    code {{ font-size: 12px; background: #f1f5f9; padding: 2px 6px; border-radius: 4px; }}
    .footer {{
      margin-top: 32px; padding-top: 20px;
      border-top: 1px solid #f0f0f0;
      font-size: 12px; color: #aaa; text-align: center;
    }}
    .footer a {{ color: #888; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="logo">
      <div class="logo-mark">H</div>
      <div>
        <div class="logo-text">hospo-mcp</div>
        <div class="logo-sub">Hospitality Intelligence</div>
      </div>
    </div>

    <h1>Connect Lightspeed POS</h1>
    <p class="subtitle">
      Link your Lightspeed O-Series account so hospo-mcp can read your sales,
      menu items, and venue data in real time.
    </p>

    {status_block}

    <div class="footer">
      <a href="/auth/status?venue_id={venue_id}">Check API status</a> &middot;
      <a href="https://apidoc.kounta.com/" target="_blank">Lightspeed API docs</a>
    </div>
  </div>
</body>
</html>"""


def _success_page(record: dict, venue_id: str) -> str:
    company = record.get("company_name") or "Your venue"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>hospo-mcp — Connected!</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #f5f5f5; color: #1a1a1a;
      min-height: 100vh; display: flex;
      align-items: center; justify-content: center; padding: 24px;
    }}
    .card {{
      background: #fff; border-radius: 12px;
      box-shadow: 0 2px 16px rgba(0,0,0,.08);
      padding: 40px; max-width: 480px; width: 100%; text-align: center;
    }}
    .checkmark {{ font-size: 56px; margin-bottom: 16px; }}
    h1 {{ font-size: 24px; font-weight: 700; margin-bottom: 8px; }}
    p {{ color: #666; line-height: 1.6; }}
    a {{
      display: inline-block; margin-top: 24px;
      padding: 12px 24px; background: #1a1a2e;
      color: #fff; text-decoration: none;
      border-radius: 8px; font-weight: 600;
    }}
  </style>
</head>
<body>
  <div class="card">
    <div class="checkmark">✅</div>
    <h1>Connected!</h1>
    <p>
      <strong>{company}</strong> is now linked to hospo-mcp.<br>
      Your AI tools can now access live sales data, menu items, and more.
    </p>
    <a href="/connect?venue_id={venue_id}">Back to connection page</a>
  </div>
</body>
</html>"""


def _error_page(error: str, description: Optional[str]) -> str:
    desc = description or "Something went wrong during the connection process."
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>hospo-mcp — Connection Error</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #f5f5f5; color: #1a1a1a;
      min-height: 100vh; display: flex;
      align-items: center; justify-content: center; padding: 24px;
    }}
    .card {{
      background: #fff; border-radius: 12px;
      box-shadow: 0 2px 16px rgba(0,0,0,.08);
      padding: 40px; max-width: 480px; width: 100%; text-align: center;
    }}
    .icon {{ font-size: 56px; margin-bottom: 16px; }}
    h1 {{ font-size: 24px; font-weight: 700; margin-bottom: 8px; color: #b91c1c; }}
    p {{ color: #666; line-height: 1.6; }}
    code {{ font-size: 13px; background: #f1f5f9; padding: 2px 6px; border-radius: 4px; }}
    a {{
      display: inline-block; margin-top: 24px;
      padding: 12px 24px; background: #1a1a2e;
      color: #fff; text-decoration: none;
      border-radius: 8px; font-weight: 600;
    }}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">⚠️</div>
    <h1>Connection Failed</h1>
    <p>{desc}<br><small>Error: <code>{error}</code></small></p>
    <a href="/connect">Try again</a>
  </div>
</body>
</html>"""
