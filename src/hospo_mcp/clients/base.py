"""Base HTTP client with mock fallback support."""

import httpx
import structlog
from typing import Any, Optional

logger = structlog.get_logger()


class BaseClient:
    """Base client for all hospo API integrations."""

    def __init__(self, base_url: str, token: str = "", use_mock: bool = True):
        self.base_url = base_url
        self.token = token
        self.use_mock = use_mock
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {"Accept": "application/json"}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=30.0,
            )
        return self._client

    async def get(self, path: str, params: dict = None) -> dict:
        if self.use_mock:
            return await self._mock_get(path, params or {})
        client = await self._get_client()
        try:
            resp = await client.get(path, params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error("api_get_error", path=path, error=str(e))
            raise

    async def post(self, path: str, data: dict) -> dict:
        if self.use_mock:
            return await self._mock_post(path, data)
        client = await self._get_client()
        try:
            resp = await client.post(path, json=data)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error("api_post_error", path=path, error=str(e))
            raise

    async def put(self, path: str, data: dict) -> dict:
        if self.use_mock:
            return await self._mock_put(path, data)
        client = await self._get_client()
        try:
            resp = await client.put(path, json=data)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error("api_put_error", path=path, error=str(e))
            raise

    async def _mock_get(self, path: str, params: dict) -> dict:
        """Override in subclasses to return mock data."""
        return {"mock": True, "path": path, "params": params}

    async def _mock_post(self, path: str, data: dict) -> dict:
        return {"mock": True, "path": path, "created": True}

    async def _mock_put(self, path: str, data: dict) -> dict:
        return {"mock": True, "path": path, "updated": True}

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
