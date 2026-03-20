"""
hospo-mcp: Model Context Protocol server for hospitality systems.

Wraps Lightspeed POS, Xero, and Deputy into a unified MCP server
that lets AI agents interact natively with your hospo tech stack.
"""

import asyncio
import sys
import structlog
import logging

from mcp.server.fastmcp import FastMCP

from .config import config
from .clients.lightspeed import LightspeedClient
from .clients.xero import XeroClient
from .clients.deputy import DeputyClient
from .tools.lightspeed_tools import register_lightspeed_tools
from .tools.xero_tools import register_xero_tools
from .tools.deputy_tools import register_deputy_tools
from .resources.hospo_resources import register_resources
from .prompts.hospo_prompts import register_prompts

# Configure logging
logging.basicConfig(level=getattr(logging, config.log_level, logging.INFO))
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(
        getattr(logging, config.log_level, logging.INFO)
    )
)
logger = structlog.get_logger()


def create_server() -> FastMCP:
    """
    Create and configure the MCP server with all integrations.
    """
    logger.info(
        "hospo_mcp.starting",
        version=config.server_version,
        use_mock=config.use_mock,
        integrations=config.integrations_status(),
    )

    # Create FastMCP server
    mcp = FastMCP(
        name=config.server_name,
        instructions="""
You are connected to hospo-mcp, a Model Context Protocol server for hospitality business systems.

Available integrations:
- **Lightspeed POS** — sales data, menu items, categories, pricing
- **Xero** — invoices, P&L, cash flow, accounts, GST
- **Deputy** — roster, timesheets, labour cost, leave management

You can use the tools to query live (or mock) data, run reports, and update records.
Use the resources for quick snapshots of key data.
Use the prompts for guided workflows like EOD reports, payroll prep, or financial reviews.

Always confirm before making write operations (price changes, invoice creation, leave approval).
        """.strip(),
    )

    # Initialise clients
    use_mock = config.use_mock
    lightspeed_client = LightspeedClient(config.lightspeed, use_mock=use_mock)
    xero_client = XeroClient(config.xero, use_mock=use_mock)
    deputy_client = DeputyClient(config.deputy, use_mock=use_mock)

    # Register tools
    register_lightspeed_tools(mcp, lightspeed_client)
    register_xero_tools(mcp, xero_client)
    register_deputy_tools(mcp, deputy_client)

    # Register resources
    register_resources(mcp, lightspeed_client, xero_client, deputy_client, config)

    # Register prompts
    register_prompts(mcp)

    logger.info("hospo_mcp.ready", tools="registered", resources="registered", prompts="registered")
    return mcp


def main():
    """Entry point — runs the MCP server over stdio (standard MCP transport)."""
    mcp = create_server()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
