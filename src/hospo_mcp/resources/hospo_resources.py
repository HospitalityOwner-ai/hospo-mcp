"""MCP resources exposing live data as readable URIs."""

import json
from mcp.server.fastmcp import FastMCP
from ..clients.lightspeed import LightspeedClient
from ..clients.xero import XeroClient
from ..clients.deputy import DeputyClient
from ..config import AppConfig
import structlog

logger = structlog.get_logger()


def register_resources(
    mcp: FastMCP,
    lightspeed: LightspeedClient,
    xero: XeroClient,
    deputy: DeputyClient,
    config: AppConfig,
):
    """Register MCP resources."""

    @mcp.resource("hospo://status")
    async def integration_status() -> str:
        """
        Integration status — which APIs are configured vs mock mode.
        """
        return json.dumps(config.integrations_status(), indent=2)

    @mcp.resource("hospo://sales/today")
    async def todays_sales() -> str:
        """Today's sales summary from Lightspeed POS."""
        result = await lightspeed.get_sales_summary()
        return json.dumps(result, indent=2)

    @mcp.resource("hospo://sales/categories")
    async def sales_categories() -> str:
        """Sales breakdown by category."""
        result = await lightspeed.get_categories()
        return json.dumps(result, indent=2)

    @mcp.resource("hospo://financials/pl")
    async def profit_loss() -> str:
        """Current month's Profit & Loss from Xero."""
        result = await xero.get_profit_loss()
        return json.dumps(result, indent=2)

    @mcp.resource("hospo://financials/outstanding")
    async def outstanding_invoices() -> str:
        """Outstanding invoices from Xero."""
        result = await xero.get_invoices(status="AUTHORISED")
        return json.dumps(result, indent=2)

    @mcp.resource("hospo://staff/roster")
    async def todays_roster() -> str:
        """Today's staff roster from Deputy."""
        result = await deputy.get_rosters()
        return json.dumps(result, indent=2)

    @mcp.resource("hospo://staff/labour-cost")
    async def labour_cost() -> str:
        """Labour cost summary for this week from Deputy."""
        result = await deputy.get_labour_cost()
        return json.dumps(result, indent=2)

    @mcp.resource("hospo://staff/pending-approvals")
    async def pending_approvals() -> str:
        """Timesheets and leave requests pending approval."""
        timesheets = await deputy.get_timesheets(status="PENDING")
        leave = await deputy.get_leave_requests(status="PENDING")
        return json.dumps({
            "pending_timesheets": timesheets,
            "pending_leave": leave,
        }, indent=2)
