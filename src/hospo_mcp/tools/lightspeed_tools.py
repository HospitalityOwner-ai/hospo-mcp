"""MCP tools for Lightspeed O-Series (Kounta) POS."""

import json
from typing import Any
from mcp.server.fastmcp import FastMCP
from ..clients.lightspeed import LightspeedClient
import structlog

logger = structlog.get_logger()


def register_lightspeed_tools(mcp: FastMCP, client: LightspeedClient):
    """Register all Lightspeed O-Series POS tools with the MCP server."""

    @mcp.tool()
    async def get_sales(
        date_from: str = "",
        date_to: str = "",
        limit: int = 50,
        site_id: str = "",
    ) -> str:
        """
        Get sales/orders from Lightspeed O-Series (Kounta) POS.

        Use this to retrieve order data for a date range. Dates should be in
        ISO 8601 format (YYYY-MM-DD). Returns a list of orders with line items,
        totals, and staff info. Optionally scope to a specific site/venue.

        Args:
            date_from: Start date (YYYY-MM-DD). Defaults to today.
            date_to: End date (YYYY-MM-DD). Defaults to today.
            limit: Maximum number of results (default 50, max 200).
            site_id: O-Series site ID to scope results to one venue. Defaults
                     to the configured LIGHTSPEED_SITE_ID.
        """
        logger.info("tool.get_sales", date_from=date_from, limit=limit, site_id=site_id)
        result = await client.get_sales(
            date_from=date_from or None,
            date_to=date_to or None,
            limit=limit,
            site_id=site_id or None,
        )
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def get_sales_summary(date: str = "") -> str:
        """
        Get an aggregated sales summary for a specific day from Lightspeed O-Series POS.

        Returns total revenue, number of transactions, average transaction value,
        and an hourly breakdown of sales. Great for end-of-day reporting.

        Args:
            date: Date to summarise (YYYY-MM-DD). Defaults to today.
        """
        logger.info("tool.get_sales_summary", date=date)
        result = await client.get_sales_summary(date=date or None)
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def get_menu_items(category: str = "") -> str:
        """
        Get products (menu items) from Lightspeed O-Series POS.

        Returns products with their prices, categories, and codes. Useful for
        pricing analysis, menu engineering, or syncing with other systems.

        Args:
            category: Filter by category name (e.g. "Food", "Wine", "Draught Beer").
                       Leave blank to get all products.
        """
        logger.info("tool.get_menu_items", category=category)
        result = await client.get_items(category=category or None)
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def get_sales_categories() -> str:
        """
        Get all sales categories and their today's totals from Lightspeed O-Series POS.

        Returns a breakdown of revenue by category (Food, Beverage, etc.)
        with today's running total for each. Great for at-a-glance dashboards.
        """
        logger.info("tool.get_sales_categories")
        result = await client.get_categories()
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def get_menu_item(item_id: str) -> str:
        """
        Get details for a specific product/menu item by its ID.

        Args:
            item_id: The O-Series product ID (e.g. "prod_001").
        """
        logger.info("tool.get_menu_item", item_id=item_id)
        result = await client.get_item_by_id(item_id)
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def get_sites() -> str:
        """
        Get all sites (venues/locations) for the company from Lightspeed O-Series.

        Returns site IDs, names, and addresses. Use these site IDs when calling
        get_sales to scope results to a specific venue.
        """
        logger.info("tool.get_sites")
        result = await client.get_sites()
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def update_item_price(item_id: str, new_price_dollars: float) -> str:
        """
        Update the price of a product in Lightspeed O-Series POS.

        ⚠️ This writes to your POS system. Double-check before calling.

        Args:
            item_id: The O-Series product ID to update.
            new_price_dollars: New price in dollars (e.g. 24.00 for $24).
        """
        logger.info("tool.update_item_price", item_id=item_id, price=new_price_dollars)
        new_price_cents = int(new_price_dollars * 100)
        result = await client.update_item_price(item_id, new_price_cents)
        return json.dumps(result, indent=2)
