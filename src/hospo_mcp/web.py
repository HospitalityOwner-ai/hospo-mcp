"""FastAPI web application — wraps hospo-mcp with OAuth routes.

Run with:
    uvicorn hospo_mcp.web:app --reload

This exposes:
  /connect                  — HTML onboarding page
  /auth/lightspeed          — OAuth redirect
  /auth/lightspeed/callback — OAuth callback
  /auth/status              — Connection status (JSON)
  /auth/disconnect          — Revoke tokens (POST)

The MCP server itself still runs over stdio (hospo_mcp.server).
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .auth.oauth_routes import register_oauth_routes
from .config import config

app = FastAPI(
    title="hospo-mcp",
    description="Hospitality MCP — OAuth onboarding and status endpoints.",
    version="0.1.0",
)

# Register all OAuth routes
register_oauth_routes(app)


@app.get("/", response_class=JSONResponse, tags=["meta"])
async def root():
    """Health check / info endpoint."""
    return {
        "service": "hospo-mcp",
        "version": "0.1.0",
        "connect": "/connect",
        "auth_status": "/auth/status",
        "integrations": config.integrations_status(),
    }
