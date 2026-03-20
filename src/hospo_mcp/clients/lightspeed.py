"""Lightspeed POS client — wraps Lightspeed O-Series (Kounta) API.

Lightspeed O-Series (formerly Kounta) is the dominant POS in Australian hospitality.
API docs: https://apidoc.kounta.com/
OAuth 2.0 credentials: developers@kounta.com

Note: K-Series (Lightspeed Restaurant) is a separate product. For K-Series support,
a future adapter will be added. O-Series is the primary integration for AU venues.

Token resolution order:
  1. Token store (tokens/{venue_id}.json) — production OAuth flow
  2. .env LIGHTSPEED_ACCESS_TOKEN — dev/testing fallback
  3. No token → mock mode
"""

from datetime import date, datetime, timedelta
from typing import Any, Optional
from .base import BaseClient
from ..config import LightspeedConfig
from ..auth.token_store import get_valid_access_token, load_tokens
import structlog

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Rich mock data — realistic Aussie pub scenario
# ---------------------------------------------------------------------------
MOCK_COMPANY = {
    "id": 1001,
    "name": "The Bidgee Hotel",
    "email": "info@bidgeehotel.com.au",
    "country": "AU",
    "timezone": "Australia/Sydney",
    "currency": "AUD",
    "mock": True,
}

MOCK_SITES = [
    {
        "id": 101,
        "name": "The Bidgee Hotel — Main Bar",
        "code": "BIDGEE-MAIN",
        "address": {
            "city": "Narrandera",
            "state": "NSW",
            "postcode": "2700",
            "country": "AU",
        },
        "active": True,
    },
    {
        "id": 102,
        "name": "The Bidgee Hotel — Bistro",
        "code": "BIDGEE-BISTRO",
        "address": {
            "city": "Narrandera",
            "state": "NSW",
            "postcode": "2700",
            "country": "AU",
        },
        "active": True,
    },
]

MOCK_ORDERS = [
    {
        "id": "order_001",
        "code": "R-10045",
        "total": 187.00,
        "tax": 17.00,
        "created_at": "2024-03-20T19:32:00+11:00",
        "completed_at": "2024-03-20T19:45:00+11:00",
        "status": "complete",
        "site_id": 101,
        "staff_id": "staff_003",
        "lines": [
            {"name": "Beef Burger", "quantity": 2, "unit_price": 24.00, "total": 48.00, "category": "Food"},
            {"name": "Pint Lager", "quantity": 4, "unit_price": 11.00, "total": 44.00, "category": "Draught Beer"},
            {"name": "House White 150ml", "quantity": 3, "unit_price": 9.00, "total": 27.00, "category": "Wine"},
            {"name": "Garlic Bread", "quantity": 2, "unit_price": 8.00, "total": 16.00, "category": "Food"},
            {"name": "Pint Pale Ale", "quantity": 2, "unit_price": 12.00, "total": 24.00, "category": "Draught Beer"},
            {"name": "House Red 150ml", "quantity": 2, "unit_price": 9.00, "total": 18.00, "category": "Wine"},
            {"name": "Tap Water", "quantity": 4, "unit_price": 0.00, "total": 0.00, "category": "Beverages"},
            {"name": "Vanilla Ice Cream", "quantity": 1, "unit_price": 10.00, "total": 10.00, "category": "Dessert"},
        ],
    },
    {
        "id": "order_002",
        "code": "R-10046",
        "total": 95.00,
        "tax": 8.64,
        "created_at": "2024-03-20T20:15:00+11:00",
        "completed_at": "2024-03-20T20:38:00+11:00",
        "status": "complete",
        "site_id": 102,
        "staff_id": "staff_001",
        "lines": [
            {"name": "Fish & Chips", "quantity": 1, "unit_price": 28.00, "total": 28.00, "category": "Food"},
            {"name": "Pint Lager", "quantity": 2, "unit_price": 11.00, "total": 22.00, "category": "Draught Beer"},
            {"name": "Kids Chicken Nuggets", "quantity": 1, "unit_price": 12.00, "total": 12.00, "category": "Food"},
            {"name": "Soft Drink", "quantity": 2, "unit_price": 6.00, "total": 12.00, "category": "Beverages"},
            {"name": "Sticky Date Pudding", "quantity": 1, "unit_price": 13.00, "total": 13.00, "category": "Dessert"},
            {"name": "Schooner Pale Ale", "quantity": 1, "unit_price": 8.00, "total": 8.00, "category": "Draught Beer"},
        ],
    },
    {
        "id": "order_003",
        "code": "R-10047",
        "total": 246.00,
        "tax": 22.36,
        "created_at": "2024-03-20T21:05:00+11:00",
        "completed_at": "2024-03-20T21:45:00+11:00",
        "status": "complete",
        "site_id": 101,
        "staff_id": "staff_002",
        "lines": [
            {"name": "Wagyu Rump 300g", "quantity": 2, "unit_price": 48.00, "total": 96.00, "category": "Food"},
            {"name": "Bottle Shiraz", "quantity": 1, "unit_price": 55.00, "total": 55.00, "category": "Wine"},
            {"name": "Side Salad", "quantity": 2, "unit_price": 9.00, "total": 18.00, "category": "Food"},
            {"name": "Crème Brûlée", "quantity": 2, "unit_price": 14.00, "total": 28.00, "category": "Dessert"},
            {"name": "Mushroom Sauce", "quantity": 2, "unit_price": 4.00, "total": 8.00, "category": "Food"},
            {"name": "House Red 150ml", "quantity": 4, "unit_price": 9.00, "total": 36.00, "category": "Wine"},
            {"name": "Still Water 500ml", "quantity": 2, "unit_price": 2.50, "total": 5.00, "category": "Beverages"},
        ],
    },
]

MOCK_CATEGORIES = [
    {"id": "cat_001", "name": "Food", "totalToday": 45200},
    {"id": "cat_002", "name": "Draught Beer", "totalToday": 28600},
    {"id": "cat_003", "name": "Wine", "totalToday": 18900},
    {"id": "cat_004", "name": "Spirits", "totalToday": 12400},
    {"id": "cat_005", "name": "Beverages", "totalToday": 3200},
    {"id": "cat_006", "name": "Dessert", "totalToday": 4800},
]

MOCK_PRODUCTS = [
    {"id": "prod_001", "name": "Beef Burger", "price": 24.00, "category": "Food", "code": "FOOD-001", "active": True},
    {"id": "prod_002", "name": "Fish & Chips", "price": 28.00, "category": "Food", "code": "FOOD-002", "active": True},
    {"id": "prod_003", "name": "Wagyu Rump 300g", "price": 48.00, "category": "Food", "code": "FOOD-003", "active": True},
    {"id": "prod_004", "name": "Kids Chicken Nuggets", "price": 12.00, "category": "Food", "code": "FOOD-004", "active": True},
    {"id": "prod_005", "name": "Garlic Bread", "price": 8.00, "category": "Food", "code": "FOOD-005", "active": True},
    {"id": "prod_006", "name": "Side Salad", "price": 9.00, "category": "Food", "code": "FOOD-006", "active": True},
    {"id": "prod_007", "name": "Pint Lager", "price": 11.00, "category": "Draught Beer", "code": "BEV-001", "active": True},
    {"id": "prod_008", "name": "Pint Pale Ale", "price": 12.00, "category": "Draught Beer", "code": "BEV-002", "active": True},
    {"id": "prod_009", "name": "Schooner Pale Ale", "price": 8.00, "category": "Draught Beer", "code": "BEV-003", "active": True},
    {"id": "prod_010", "name": "House White 150ml", "price": 9.00, "category": "Wine", "code": "WIN-001", "active": True},
    {"id": "prod_011", "name": "House Red 150ml", "price": 9.00, "category": "Wine", "code": "WIN-002", "active": True},
    {"id": "prod_012", "name": "Bottle Shiraz", "price": 55.00, "category": "Wine", "code": "WIN-003", "active": True},
    {"id": "prod_013", "name": "Crème Brûlée", "price": 14.00, "category": "Dessert", "code": "DES-001", "active": True},
    {"id": "prod_014", "name": "Sticky Date Pudding", "price": 13.00, "category": "Dessert", "code": "DES-002", "active": True},
    {"id": "prod_015", "name": "Soft Drink", "price": 6.00, "category": "Beverages", "code": "BEV-010", "active": True},
    {"id": "prod_016", "name": "Still Water 500ml", "price": 2.50, "category": "Beverages", "code": "BEV-011", "active": True},
]

MOCK_SUMMARY = {
    "date": str(date.today()),
    "totalSales": {"amount": 108300, "currencyCode": "AUD"},
    "totalTax": {"amount": 9845, "currencyCode": "AUD"},
    "totalTransactions": 42,
    "averageTransaction": {"amount": 2578, "currencyCode": "AUD"},
    "topCategory": "Food",
    "hourlyBreakdown": {
        "12:00": 8200, "13:00": 15400, "14:00": 6100, "15:00": 3200,
        "16:00": 4800, "17:00": 9600, "18:00": 18700, "19:00": 22400,
        "20:00": 15600, "21:00": 4300,
    },
}


class LightspeedClient(BaseClient):
    """Client for Lightspeed O-Series (formerly Kounta) POS.

    O-Series is the dominant point-of-sale in Australian hospitality.
    Acquired from Kounta by Lightspeed in 2019; the underlying API remains
    at api.kounta.com and uses OAuth 2.0 Bearer tokens.

    Contact developers@kounta.com for API credentials.
    API docs: https://apidoc.kounta.com/

    Token resolution order:
      1. Token store (tokens/{venue_id}.json) — production OAuth flow
      2. .env LIGHTSPEED_ACCESS_TOKEN — dev/testing fallback
      3. No token → mock mode
    """

    def __init__(
        self,
        cfg: LightspeedConfig,
        use_mock: bool = True,
        venue_id: str = "default",
    ):
        self._cfg = cfg
        self._venue_id = venue_id

        # Check token store first; fall back to .env token
        stored = load_tokens(venue_id)
        token = (stored or {}).get("access_token") or cfg.access_token
        site_id = (stored or {}).get("site_id") or cfg.site_id or "MOCK_SITE"

        super().__init__(
            base_url=cfg.base_url,
            token=token,
            use_mock=use_mock or not bool(token and site_id != "MOCK_SITE"),
        )
        self.site_id = site_id

    async def _ensure_fresh_token(self) -> None:
        """Silently refresh the access token if it's expired."""
        if self._cfg.client_id and self._cfg.client_secret:
            fresh = await get_valid_access_token(
                self._venue_id,
                self._cfg.client_id,
                self._cfg.client_secret,
            )
            if fresh and fresh != self.token:
                logger.info("lightspeed.token_refreshed", venue_id=self._venue_id)
                self.token = fresh
                # Force new httpx client with updated token
                if self._client:
                    await self._client.aclose()
                    self._client = None

    # ------------------------------------------------------------------
    # Overrides to inject token refresh before real API calls
    # ------------------------------------------------------------------

    async def get(self, path: str, params: dict = None) -> dict:
        if not self.use_mock:
            await self._ensure_fresh_token()
        return await super().get(path, params)

    async def post(self, path: str, data: dict) -> dict:
        if not self.use_mock:
            await self._ensure_fresh_token()
        return await super().post(path, data)

    async def put(self, path: str, data: dict) -> dict:
        if not self.use_mock:
            await self._ensure_fresh_token()
        return await super().put(path, data)

    # ------------------------------------------------------------------
    # Company / venue discovery
    # ------------------------------------------------------------------

    async def get_company(self) -> dict:
        """Get the authenticated company (merchant) record."""
        return await self.get("/companies/me.json", {})

    async def get_sites(self) -> dict:
        """Get all sites (venues/locations) for the company."""
        return await self.get("/companies/me/sites.json", {})

    # ------------------------------------------------------------------
    # Orders / Sales
    # ------------------------------------------------------------------

    async def get_sales(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 50,
        site_id: Optional[str] = None,
    ) -> dict:
        """Get orders/transactions for a date range.

        Uses the site-scoped endpoint when site_id is provided, otherwise
        falls back to the company-wide orders endpoint.
        """
        sid = site_id or self.site_id
        if sid and sid != "MOCK_SITE":
            path = f"/companies/me/sites/{sid}/orders.json"
        else:
            path = "/companies/me/orders.json"

        params: dict = {"limit": limit}
        if date_from:
            params["created_at_min"] = date_from
        if date_to:
            params["created_at_max"] = date_to
        return await self.get(path, params)

    async def get_sales_summary(self, date: Optional[str] = None) -> dict:
        """Get aggregated sales summary for a day."""
        sid = self.site_id if self.site_id != "MOCK_SITE" else None
        if sid:
            path = f"/companies/me/sites/{sid}/orders.json"
        else:
            path = "/companies/me/orders.json"
        return await self.get(path, {"summary": True, "date": date})

    # ------------------------------------------------------------------
    # Products / Menu
    # ------------------------------------------------------------------

    async def get_items(self, category: Optional[str] = None) -> dict:
        """Get products (menu items)."""
        params: dict = {}
        if category:
            params["category"] = category
        return await self.get("/companies/me/products.json", params)

    async def get_item_by_id(self, item_id: str) -> dict:
        """Get a specific product by ID."""
        return await self.get(f"/companies/me/products/{item_id}.json", {})

    async def update_item_price(self, item_id: str, new_price_cents: int) -> dict:
        """Update a product price (price in cents, stored as dollars to Kounta API)."""
        price_dollars = new_price_cents / 100
        return await self.put(
            f"/companies/me/products/{item_id}.json",
            {"price": price_dollars},
        )

    # ------------------------------------------------------------------
    # Categories
    # ------------------------------------------------------------------

    async def get_categories(self) -> dict:
        """Get product categories."""
        return await self.get("/companies/me/categories.json", {})

    # ------------------------------------------------------------------
    # Mock overrides
    # ------------------------------------------------------------------

    async def _mock_get(self, path: str, params: dict) -> dict:
        # Company
        if path == "/companies/me.json":
            return MOCK_COMPANY

        # Sites
        if path == "/companies/me/sites.json":
            return {"sites": MOCK_SITES, "total": len(MOCK_SITES), "mock": True}

        # Orders / sales — summary or list
        if "orders.json" in path:
            if params.get("summary"):
                return MOCK_SUMMARY
            return {"orders": MOCK_ORDERS, "total": len(MOCK_ORDERS), "mock": True}

        # Single product
        if "/products/" in path and not path.endswith("products.json"):
            prod_id = path.split("/products/")[1].rstrip(".json")
            product = next((p for p in MOCK_PRODUCTS if p["id"] == prod_id), MOCK_PRODUCTS[0])
            return {"product": product, "mock": True}

        # Products list
        if "products.json" in path:
            products = MOCK_PRODUCTS
            if params.get("category"):
                products = [p for p in products if p["category"] == params["category"]]
            return {"products": products, "total": len(products), "mock": True}

        # Categories
        if "categories.json" in path:
            return {"categories": MOCK_CATEGORIES, "total": len(MOCK_CATEGORIES), "mock": True}

        return {"mock": True, "path": path}

    async def _mock_put(self, path: str, data: dict) -> dict:
        return {"mock": True, "updated": True, "path": path, "data": data}
