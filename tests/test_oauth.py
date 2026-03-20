"""Tests for OAuth 2.0 endpoints and token store.

Mocks out the Lightspeed token exchange so no real HTTP calls are made.
"""

import json
import os
import time
import tempfile
import pytest
import httpx
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_token_dir(tmp_path, monkeypatch):
    """Use a temp directory for token storage in every test."""
    monkeypatch.setenv("HOSPO_TOKEN_DIR", str(tmp_path / "tokens"))
    # Reload token_store so TOKEN_DIR picks up the new env var
    import importlib
    import hospo_mcp.auth.token_store as ts
    ts.TOKEN_DIR = Path(os.getenv("HOSPO_TOKEN_DIR", "tokens"))
    yield tmp_path / "tokens"


@pytest.fixture
def oauth_env(monkeypatch):
    """Inject fake OAuth credentials."""
    monkeypatch.setenv("LIGHTSPEED_CLIENT_ID", "test_client_id")
    monkeypatch.setenv("LIGHTSPEED_CLIENT_SECRET", "test_client_secret")
    monkeypatch.setenv(
        "LIGHTSPEED_REDIRECT_URI",
        "http://localhost:8000/auth/lightspeed/callback",
    )


@pytest.fixture
def test_app():
    """Create a test FastAPI app with OAuth routes registered."""
    from fastapi import FastAPI
    from hospo_mcp.auth.oauth_routes import register_oauth_routes
    app = FastAPI()
    register_oauth_routes(app)
    return app


@pytest.fixture
def client(test_app):
    return TestClient(test_app, follow_redirects=False)


# ---------------------------------------------------------------------------
# Token store unit tests
# ---------------------------------------------------------------------------

class TestTokenStore:
    def test_save_and_load_tokens(self, isolated_token_dir):
        from hospo_mcp.auth.token_store import save_tokens, load_tokens
        data = {
            "access_token": "abc123",
            "refresh_token": "refresh456",
            "expires_at": time.time() + 3600,
            "site_id": "site_1",
            "company_name": "The Bidgee Hotel",
        }
        save_tokens("venue1", data)
        loaded = load_tokens("venue1")
        assert loaded is not None
        assert loaded["access_token"] == "abc123"
        assert loaded["company_name"] == "The Bidgee Hotel"

    def test_load_missing_returns_none(self, isolated_token_dir):
        from hospo_mcp.auth.token_store import load_tokens
        assert load_tokens("nonexistent") is None

    def test_delete_tokens(self, isolated_token_dir):
        from hospo_mcp.auth.token_store import save_tokens, delete_tokens, load_tokens
        save_tokens("venue2", {"access_token": "tok"})
        assert delete_tokens("venue2") is True
        assert load_tokens("venue2") is None

    def test_delete_nonexistent_returns_false(self, isolated_token_dir):
        from hospo_mcp.auth.token_store import delete_tokens
        assert delete_tokens("ghost") is False

    def test_is_connected_true(self, isolated_token_dir):
        from hospo_mcp.auth.token_store import save_tokens, is_connected
        save_tokens("venue3", {"access_token": "valid_tok"})
        assert is_connected("venue3") is True

    def test_is_connected_false_when_missing(self, isolated_token_dir):
        from hospo_mcp.auth.token_store import is_connected
        assert is_connected("nobody") is False

    def test_token_expired_true(self):
        from hospo_mcp.auth.token_store import token_expired
        tokens = {"access_token": "x", "expires_at": time.time() - 100}
        assert token_expired(tokens) is True

    def test_token_expired_false(self):
        from hospo_mcp.auth.token_store import token_expired
        tokens = {"access_token": "x", "expires_at": time.time() + 3600}
        assert token_expired(tokens) is False

    def test_token_expired_no_expiry(self):
        from hospo_mcp.auth.token_store import token_expired
        # No expires_at — assume still valid
        assert token_expired({"access_token": "x"}) is False

    def test_build_token_record(self):
        from hospo_mcp.auth.token_store import build_token_record
        raw = {
            "access_token": "new_tok",
            "refresh_token": "new_refresh",
            "expires_in": 7200,
            "company_name": "Test Pub",
            "site_id": "site_99",
        }
        record = build_token_record(raw)
        assert record["access_token"] == "new_tok"
        assert record["refresh_token"] == "new_refresh"
        assert record["company_name"] == "Test Pub"
        assert record["site_id"] == "site_99"
        assert record["expires_at"] > time.time()

    def test_venue_id_sanitised(self, isolated_token_dir):
        """Path traversal characters should be stripped from venue_id."""
        from hospo_mcp.auth.token_store import save_tokens, load_tokens
        save_tokens("../evil", {"access_token": "x"})
        # Should have been sanitised to "evil"
        loaded = load_tokens("evil")
        assert loaded is not None

    async def test_get_valid_access_token_not_expired(self, isolated_token_dir):
        from hospo_mcp.auth.token_store import save_tokens, get_valid_access_token
        save_tokens("v1", {
            "access_token": "valid",
            "refresh_token": "ref",
            "expires_at": time.time() + 3600,
        })
        tok = await get_valid_access_token("v1", "cid", "csecret")
        assert tok == "valid"

    async def test_get_valid_access_token_expired_refreshes(self, isolated_token_dir):
        from hospo_mcp.auth.token_store import save_tokens, get_valid_access_token
        save_tokens("v2", {
            "access_token": "old_tok",
            "refresh_token": "old_refresh",
            "expires_at": time.time() - 100,  # expired
            "site_id": "site_1",
            "company_name": "Test Pub",
        })
        mock_raw = {
            "access_token": "new_tok",
            "refresh_token": "new_refresh",
            "expires_in": 7200,
        }
        with patch(
            "hospo_mcp.auth.token_store.refresh_access_token",
            new=AsyncMock(return_value=mock_raw),
        ):
            tok = await get_valid_access_token("v2", "cid", "csecret")
        assert tok == "new_tok"

    async def test_get_valid_access_token_no_tokens_returns_none(self, isolated_token_dir):
        from hospo_mcp.auth.token_store import get_valid_access_token
        tok = await get_valid_access_token("nobody", "cid", "csecret")
        assert tok is None


# ---------------------------------------------------------------------------
# OAuth endpoint tests
# ---------------------------------------------------------------------------

class TestAuthRedirect:
    def test_redirects_to_lightspeed(self, client, oauth_env):
        resp = client.get("/auth/lightspeed")
        assert resp.status_code == 302
        location = resp.headers["location"]
        assert "api.kounta.com" in location
        assert "response_type=code" in location
        assert "client_id=test_client_id" in location
        assert "redirect_uri=" in location
        assert "state=" in location

    def test_state_is_uuid_format(self, client, oauth_env):
        import re
        resp = client.get("/auth/lightspeed")
        location = resp.headers["location"]
        # state is "{uuid}:{venue_id}" — extract it
        from urllib.parse import urlparse, parse_qs
        qs = parse_qs(urlparse(location).query)
        state = qs["state"][0]
        # Should start with a UUID
        uuid_part = state.split(":")[0]
        uuid_re = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
        )
        assert uuid_re.match(uuid_part)

    def test_no_credentials_returns_501(self, client, monkeypatch):
        monkeypatch.delenv("LIGHTSPEED_CLIENT_ID", raising=False)
        monkeypatch.delenv("LIGHTSPEED_CLIENT_SECRET", raising=False)
        resp = client.get("/auth/lightspeed")
        assert resp.status_code == 501

    def test_venue_id_passed_in_state(self, client, oauth_env):
        from urllib.parse import urlparse, parse_qs
        resp = client.get("/auth/lightspeed?venue_id=my_venue")
        location = resp.headers["location"]
        qs = parse_qs(urlparse(location).query)
        state = qs["state"][0]
        assert state.endswith(":my_venue")


class TestAuthCallback:
    def _make_state(self, venue_id: str = "default") -> str:
        import uuid
        return f"{uuid.uuid4()}:{venue_id}"

    async def test_callback_stores_tokens(self, client, oauth_env, isolated_token_dir):
        mock_raw = {
            "access_token": "live_tok",
            "refresh_token": "live_refresh",
            "expires_in": 7200,
            "company_name": "The Pub",
            "site_id": "site_42",
        }
        with patch(
            "hospo_mcp.auth.oauth_routes.exchange_code_for_tokens",
            new=AsyncMock(return_value=mock_raw),
        ):
            resp = client.get(
                "/auth/lightspeed/callback",
                params={"code": "auth_code_xyz", "state": self._make_state()},
            )
        assert resp.status_code == 200
        assert "Connected" in resp.text

        # Tokens should be on disk
        from hospo_mcp.auth.token_store import load_tokens
        stored = load_tokens("default")
        assert stored is not None
        assert stored["access_token"] == "live_tok"

    async def test_callback_with_error_param(self, client, oauth_env):
        resp = client.get(
            "/auth/lightspeed/callback",
            params={"error": "access_denied", "error_description": "User denied access"},
        )
        assert resp.status_code == 400
        assert "access_denied" in resp.text

    async def test_callback_missing_code(self, client, oauth_env):
        resp = client.get("/auth/lightspeed/callback")
        assert resp.status_code == 400

    async def test_callback_exchange_failure(self, client, oauth_env):
        with patch(
            "hospo_mcp.auth.oauth_routes.exchange_code_for_tokens",
            new=AsyncMock(side_effect=Exception("Network error")),
        ):
            resp = client.get(
                "/auth/lightspeed/callback",
                params={"code": "bad_code", "state": self._make_state()},
            )
        assert resp.status_code == 502

    async def test_callback_venue_id_from_state(self, client, oauth_env, isolated_token_dir):
        mock_raw = {
            "access_token": "tok",
            "refresh_token": "ref",
            "expires_in": 3600,
            "company_name": "Another Pub",
            "site_id": "site_55",
        }
        with patch(
            "hospo_mcp.auth.oauth_routes.exchange_code_for_tokens",
            new=AsyncMock(return_value=mock_raw),
        ):
            resp = client.get(
                "/auth/lightspeed/callback",
                params={"code": "code_abc", "state": self._make_state("venue_xyz")},
            )
        assert resp.status_code == 200
        from hospo_mcp.auth.token_store import load_tokens
        stored = load_tokens("venue_xyz")
        assert stored is not None


class TestAuthStatus:
    def test_disconnected_when_no_tokens(self, client, isolated_token_dir):
        resp = client.get("/auth/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "disconnected"

    def test_connected_when_tokens_stored(self, client, isolated_token_dir):
        from hospo_mcp.auth.token_store import save_tokens
        save_tokens("default", {
            "access_token": "tok",
            "company_name": "My Pub",
            "site_id": "site_1",
        })
        resp = client.get("/auth/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "connected"
        assert data["company_name"] == "My Pub"

    def test_status_for_specific_venue(self, client, isolated_token_dir):
        from hospo_mcp.auth.token_store import save_tokens
        save_tokens("venue_a", {"access_token": "tok_a", "company_name": "A"})
        resp = client.get("/auth/status?venue_id=venue_a")
        assert resp.json()["status"] == "connected"

        resp2 = client.get("/auth/status?venue_id=venue_b")
        assert resp2.json()["status"] == "disconnected"


class TestAuthDisconnect:
    def test_disconnect_removes_tokens(self, client, isolated_token_dir):
        from hospo_mcp.auth.token_store import save_tokens, is_connected
        save_tokens("default", {"access_token": "tok"})
        assert is_connected("default") is True

        resp = client.post("/auth/disconnect")
        assert resp.status_code == 200
        assert resp.json()["status"] == "disconnected"
        assert is_connected("default") is False

    def test_disconnect_when_not_connected(self, client, isolated_token_dir):
        # Should not error even if not connected
        resp = client.post("/auth/disconnect")
        assert resp.status_code == 200


class TestConnectPage:
    def test_connect_page_renders(self, client, oauth_env):
        resp = client.get("/connect")
        assert resp.status_code == 200
        assert "hospo-mcp" in resp.text
        assert "Lightspeed" in resp.text

    def test_connect_page_shows_connect_button_when_disconnected(
        self, client, oauth_env, isolated_token_dir
    ):
        resp = client.get("/connect")
        assert "Connect your Lightspeed account" in resp.text

    def test_connect_page_shows_connected_status(
        self, client, oauth_env, isolated_token_dir
    ):
        from hospo_mcp.auth.token_store import save_tokens
        save_tokens("default", {
            "access_token": "tok",
            "company_name": "The Bidgee Hotel",
            "site_id": "site_101",
        })
        resp = client.get("/connect")
        assert "The Bidgee Hotel" in resp.text
        assert "Disconnect" in resp.text

    def test_connect_page_shows_warning_when_no_oauth_config(
        self, client, monkeypatch, isolated_token_dir
    ):
        monkeypatch.delenv("LIGHTSPEED_CLIENT_ID", raising=False)
        monkeypatch.delenv("LIGHTSPEED_CLIENT_SECRET", raising=False)
        resp = client.get("/connect")
        assert "OAuth not configured" in resp.text


# ---------------------------------------------------------------------------
# LightspeedClient token resolution tests
# ---------------------------------------------------------------------------

class TestLightspeedClientTokenResolution:
    def test_uses_stored_token_over_env(self, isolated_token_dir, monkeypatch):
        monkeypatch.setenv("LIGHTSPEED_ACCESS_TOKEN", "env_token")
        from hospo_mcp.auth.token_store import save_tokens
        save_tokens("default", {
            "access_token": "stored_token",
            "site_id": "site_1",
        })
        # Reimport to get fresh config
        from hospo_mcp.config import LightspeedConfig
        from hospo_mcp.clients.lightspeed import LightspeedClient
        cfg = LightspeedConfig()
        client = LightspeedClient(cfg, use_mock=False, venue_id="default")
        assert client.token == "stored_token"
        assert client.site_id == "site_1"

    def test_falls_back_to_env_token(self, isolated_token_dir, monkeypatch):
        monkeypatch.setenv("LIGHTSPEED_ACCESS_TOKEN", "env_token")
        monkeypatch.setenv("LIGHTSPEED_SITE_ID", "env_site")
        # No stored tokens
        from hospo_mcp.config import LightspeedConfig
        from hospo_mcp.clients.lightspeed import LightspeedClient
        cfg = LightspeedConfig()
        client = LightspeedClient(cfg, use_mock=False, venue_id="nobody")
        assert client.token == "env_token"

    def test_mock_mode_when_no_token(self, isolated_token_dir, monkeypatch):
        monkeypatch.delenv("LIGHTSPEED_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("LIGHTSPEED_SITE_ID", raising=False)
        from hospo_mcp.config import LightspeedConfig
        from hospo_mcp.clients.lightspeed import LightspeedClient
        cfg = LightspeedConfig()
        client = LightspeedClient(cfg, use_mock=False, venue_id="nobody")
        # No token + no site = mock mode
        assert client.use_mock is True

    async def test_mock_still_works_with_no_credentials(self, isolated_token_dir, monkeypatch):
        monkeypatch.delenv("LIGHTSPEED_ACCESS_TOKEN", raising=False)
        from hospo_mcp.config import LightspeedConfig
        from hospo_mcp.clients.lightspeed import LightspeedClient
        cfg = LightspeedConfig()
        client = LightspeedClient(cfg, use_mock=True)
        result = await client.get_company()
        assert result["mock"] is True
