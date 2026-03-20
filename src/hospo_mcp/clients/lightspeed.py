"""Lightspeed POS client — wraps Lightspeed Restaurant / K-Series API."""

from datetime import date, datetime, timedelta
from typing import Any, Optional
from .base import BaseClient
from ..config import LightspeedConfig
import structlog

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Rich mock data — realistic hospo scenario
# ---------------------------------------------------------------------------
MOCK_SALES = [
    {
        "id": "sale_001",
        "receiptNumber": "R-10045",
        "totalMoney": {"amount": 18700, "currencyCode": "AUD"},
        "taxMoney": {"amount": 1700, "currencyCode": "AUD"},
        "createdAt": "2024-03-20T19:32:00+11:00",
        "status": "CLOSED",
        "employeeId": "emp_003",
        "items": [
            {"name": "Beef Burger", "quantity": 2, "price": 2400, "category": "Food"},
            {"name": "Pint Lager", "quantity": 4, "price": 1100, "category": "Draught Beer"},
            {"name": "House White 150ml", "quantity": 3, "price": 900, "category": "Wine"},
        ],
    },
    {
        "id": "sale_002",
        "receiptNumber": "R-10046",
        "totalMoney": {"amount": 9500, "currencyCode": "AUD"},
        "taxMoney": {"amount": 864, "currencyCode": "AUD"},
        "createdAt": "2024-03-20T20:15:00+11:00",
        "status": "CLOSED",
        "employeeId": "emp_001",
        "items": [
            {"name": "Fish & Chips", "quantity": 1, "price": 2800, "category": "Food"},
            {"name": "Pint Lager", "quantity": 2, "price": 1100, "category": "Draught Beer"},
            {"name": "Kids Chicken Nuggets", "quantity": 1, "price": 1200, "category": "Food"},
            {"name": "Soft Drink", "quantity": 2, "price": 600, "category": "Beverages"},
        ],
    },
    {
        "id": "sale_003",
        "receiptNumber": "R-10047",
        "totalMoney": {"amount": 24600, "currencyCode": "AUD"},
        "taxMoney": {"amount": 2236, "currencyCode": "AUD"},
        "createdAt": "2024-03-20T21:05:00+11:00",
        "status": "CLOSED",
        "employeeId": "emp_002",
        "items": [
            {"name": "Wagyu Rump 300g", "quantity": 2, "price": 4800, "category": "Food"},
            {"name": "Bottle Shiraz", "quantity": 1, "price": 5500, "category": "Wine"},
            {"name": "Side Salad", "quantity": 2, "price": 900, "category": "Food"},
            {"name": "Crème Brûlée", "quantity": 2, "price": 1400, "category": "Dessert"},
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

MOCK_ITEMS = [
    {"id": "item_001", "name": "Beef Burger", "price": 2400, "category": "Food", "sku": "FOOD-001"},
    {"id": "item_002", "name": "Fish & Chips", "price": 2800, "category": "Food", "sku": "FOOD-002"},
    {"id": "item_003", "name": "Wagyu Rump 300g", "price": 4800, "category": "Food", "sku": "FOOD-003"},
    {"id": "item_004", "name": "Pint Lager", "price": 1100, "category": "Draught Beer", "sku": "BEV-001"},
    {"id": "item_005", "name": "Pint Pale Ale", "price": 1200, "category": "Draught Beer", "sku": "BEV-002"},
    {"id": "item_006", "name": "House White 150ml", "price": 900, "category": "Wine", "sku": "WIN-001"},
    {"id": "item_007", "name": "Bottle Shiraz", "price": 5500, "category": "Wine", "sku": "WIN-002"},
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
    """Client for Lightspeed POS (Restaurant / K-Series)."""

    def __init__(self, cfg: LightspeedConfig, use_mock: bool = True):
        super().__init__(
            base_url=cfg.base_url,
            token=cfg.access_token,
            use_mock=use_mock or not cfg.configured,
        )
        self.account_id = cfg.account_id or "MOCK_ACCT"

    async def get_sales(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 50,
    ) -> dict:
        """Get sales/transactions for a date range."""
        path = f"/Account/{self.account_id}/Sale.json"
        params = {"limit": limit}
        if date_from:
            params["timeStamp"] = f">={date_from}"
        result = await self.get(path, params)
        return result

    async def get_sales_summary(self, date: Optional[str] = None) -> dict:
        """Get aggregated sales summary for a day."""
        path = f"/Account/{self.account_id}/Sale.json"
        result = await self.get(path, {"summary": True, "date": date})
        return result

    async def get_items(self, category: Optional[str] = None) -> dict:
        """Get menu items / products."""
        path = f"/Account/{self.account_id}/Item.json"
        params = {}
        if category:
            params["category"] = category
        return await self.get(path, params)

    async def get_categories(self) -> dict:
        """Get item categories."""
        path = f"/Account/{self.account_id}/Category.json"
        return await self.get(path, {})

    async def get_item_by_id(self, item_id: str) -> dict:
        """Get a specific item by ID."""
        path = f"/Account/{self.account_id}/Item/{item_id}.json"
        return await self.get(path, {})

    async def update_item_price(self, item_id: str, new_price_cents: int) -> dict:
        """Update an item price (in cents)."""
        path = f"/Account/{self.account_id}/Item/{item_id}.json"
        return await self.put(path, {"price": new_price_cents})

    # ------------------------------------------------------------------
    # Mock overrides
    # ------------------------------------------------------------------

    async def _mock_get(self, path: str, params: dict) -> dict:
        if "Sale.json" in path:
            if params.get("summary"):
                return MOCK_SUMMARY
            return {"Sale": MOCK_SALES, "total": len(MOCK_SALES), "mock": True}
        if "Item.json" in path:
            items = MOCK_ITEMS
            if params.get("category"):
                items = [i for i in items if i["category"] == params["category"]]
            return {"Item": items, "total": len(items), "mock": True}
        if "Category.json" in path:
            return {"Category": MOCK_CATEGORIES, "total": len(MOCK_CATEGORIES), "mock": True}
        if "/Item/" in path:
            item_id = path.split("/Item/")[1].rstrip(".json")
            item = next((i for i in MOCK_ITEMS if i["id"] == item_id), MOCK_ITEMS[0])
            return {"Item": item, "mock": True}
        return {"mock": True, "path": path}

    async def _mock_put(self, path: str, data: dict) -> dict:
        return {"mock": True, "updated": True, "path": path, "data": data}
