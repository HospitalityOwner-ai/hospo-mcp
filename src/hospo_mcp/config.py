"""Configuration management for hospo-mcp."""

import os
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class LightspeedConfig:
    """Lightspeed O-Series (formerly Kounta) POS config.

    O-Series is the dominant POS in Australian hospitality.
    Credentials obtained via OAuth 2.0 — contact developers@kounta.com.
    API docs: https://apidoc.kounta.com/

    Token resolution order for the client:
      1. Token store  (tokens/{venue_id}.json) — production OAuth flow
      2. LIGHTSPEED_ACCESS_TOKEN env var        — dev/testing fallback
      3. No token → mock mode

    Note: LIGHTSPEED_ACCESS_TOKEN is optional if you use the OAuth connect
    flow (recommended for production). It's kept as a fallback for local dev.

    K-Series (Lightspeed Restaurant) uses a different API and will be
    supported via a separate adapter in a future release.
    """
    # OAuth app credentials — required to run the /auth/lightspeed flow
    client_id: str = field(default_factory=lambda: os.getenv("LIGHTSPEED_CLIENT_ID", ""))
    client_secret: str = field(default_factory=lambda: os.getenv("LIGHTSPEED_CLIENT_SECRET", ""))

    # Dev/testing fallback — not needed in production (use OAuth flow instead)
    access_token: str = field(default_factory=lambda: os.getenv("LIGHTSPEED_ACCESS_TOKEN", ""))
    refresh_token: str = field(default_factory=lambda: os.getenv("LIGHTSPEED_REFRESH_TOKEN", ""))
    site_id: str = field(default_factory=lambda: os.getenv("LIGHTSPEED_SITE_ID", ""))

    @property
    def base_url(self) -> str:
        return os.getenv("LIGHTSPEED_BASE_URL", "https://api.kounta.com/v1")

    @property
    def configured(self) -> bool:
        """True if OAuth app is configured (even without a stored token yet)."""
        return bool(self.client_id and self.client_secret)

    @property
    def has_token(self) -> bool:
        """True if a direct access token is available via env (dev mode)."""
        return bool(self.access_token)


@dataclass
class XeroConfig:
    """Xero accounting config."""
    client_id: str = field(default_factory=lambda: os.getenv("XERO_CLIENT_ID", ""))
    client_secret: str = field(default_factory=lambda: os.getenv("XERO_CLIENT_SECRET", ""))
    access_token: str = field(default_factory=lambda: os.getenv("XERO_ACCESS_TOKEN", ""))
    refresh_token: str = field(default_factory=lambda: os.getenv("XERO_REFRESH_TOKEN", ""))
    tenant_id: str = field(default_factory=lambda: os.getenv("XERO_TENANT_ID", ""))
    sandbox: bool = field(default_factory=lambda: os.getenv("XERO_SANDBOX", "true").lower() == "true")

    @property
    def base_url(self) -> str:
        return "https://api.xero.com/api.xro/2.0"

    @property
    def configured(self) -> bool:
        return bool(self.access_token and self.tenant_id)


@dataclass
class DeputyConfig:
    """Deputy workforce management config."""
    api_key: str = field(default_factory=lambda: os.getenv("DEPUTY_API_KEY", ""))
    subdomain: str = field(default_factory=lambda: os.getenv("DEPUTY_SUBDOMAIN", ""))
    sandbox: bool = field(default_factory=lambda: os.getenv("DEPUTY_SANDBOX", "true").lower() == "true")

    @property
    def base_url(self) -> str:
        if self.subdomain:
            return f"https://{self.subdomain}.deputy.com/api/v1"
        return "https://once.deputy.com/api/v1"

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.subdomain)


@dataclass
class AppConfig:
    """Top-level application config."""
    lightspeed: LightspeedConfig = field(default_factory=LightspeedConfig)
    xero: XeroConfig = field(default_factory=XeroConfig)
    deputy: DeputyConfig = field(default_factory=DeputyConfig)
    use_mock: bool = field(
        default_factory=lambda: os.getenv("USE_MOCK_DATA", "true").lower() == "true"
    )
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    server_name: str = "hospo-mcp"
    server_version: str = "0.1.0"

    def integrations_status(self) -> dict:
        from .auth.token_store import is_connected
        ls_connected = is_connected("default")
        ls_mock = self.use_mock or (
            not self.lightspeed.has_token and not ls_connected
        )
        return {
            "lightspeed": {
                "configured": self.lightspeed.configured or ls_connected,
                "oauth_connected": ls_connected,
                "mock": ls_mock,
                "series": "O-Series (Kounta)",
            },
            "xero": {
                "configured": self.xero.configured,
                "mock": self.use_mock or not self.xero.configured,
            },
            "deputy": {
                "configured": self.deputy.configured,
                "mock": self.use_mock or not self.deputy.configured,
            },
        }


# Singleton
config = AppConfig()
