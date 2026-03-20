"""MCP tools for Xero accounting."""

import json
from mcp.server.fastmcp import FastMCP
from ..clients.xero import XeroClient
import structlog

logger = structlog.get_logger()


def register_xero_tools(mcp: FastMCP, client: XeroClient):
    """Register all Xero tools with the MCP server."""

    @mcp.tool()
    async def get_chart_of_accounts() -> str:
        """
        Get the chart of accounts from Xero.

        Returns all accounts with their codes, names, types, and current balances.
        Useful for understanding the financial structure of the business.
        """
        logger.info("tool.get_chart_of_accounts")
        result = await client.get_accounts()
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def get_invoices(
        status: str = "",
        invoice_type: str = "",
    ) -> str:
        """
        Get invoices and bills from Xero.

        Args:
            status: Filter by status — DRAFT, SUBMITTED, AUTHORISED, PAID, VOIDED.
                    Leave blank for all.
            invoice_type: ACCREC (sales invoices) or ACCPAY (bills/supplier invoices).
                          Leave blank for both.
        """
        logger.info("tool.get_invoices", status=status, invoice_type=invoice_type)
        result = await client.get_invoices(
            status=status or None,
            invoice_type=invoice_type or None,
        )
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def get_outstanding_invoices() -> str:
        """
        Get all outstanding (unpaid) invoices from Xero.

        Returns invoices with an amount still due. Useful for cash flow
        monitoring and follow-up on overdue accounts.
        """
        logger.info("tool.get_outstanding_invoices")
        result = await client.get_invoices(status="AUTHORISED")
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def get_profit_and_loss(
        from_date: str = "",
        to_date: str = "",
    ) -> str:
        """
        Get the Profit & Loss report from Xero.

        Returns revenue, cost of goods, gross profit, expenses, and net profit
        with margin percentages. Perfect for financial performance review.

        Args:
            from_date: Start date (YYYY-MM-DD). Defaults to start of current month.
            to_date: End date (YYYY-MM-DD). Defaults to today.
        """
        logger.info("tool.get_profit_and_loss", from_date=from_date, to_date=to_date)
        result = await client.get_profit_loss(
            from_date=from_date or None,
            to_date=to_date or None,
        )
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def get_cash_flow() -> str:
        """
        Get the cash flow summary from Xero.

        Returns opening balance, total receipts, total payments, and
        closing balance for the current period.
        """
        logger.info("tool.get_cash_flow")
        result = await client.get_cash_flow()
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def get_suppliers() -> str:
        """
        Get all suppliers/vendors from Xero contacts.

        Returns supplier names, email addresses, and contact details.
        """
        logger.info("tool.get_suppliers")
        result = await client.get_contacts(is_supplier=True)
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def get_gst_summary() -> str:
        """
        Get the GST / BAS summary from Xero.

        Returns GST collected on sales, GST paid on purchases, and
        net GST liability for BAS lodgement.
        """
        logger.info("tool.get_gst_summary")
        result = await client.get_gst_summary()
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def create_invoice(
        contact_name: str,
        description: str,
        quantity: float,
        unit_amount: float,
        account_code: str = "200",
        invoice_type: str = "ACCREC",
    ) -> str:
        """
        Create a new invoice or bill in Xero.

        ⚠️ This writes to your Xero account. Double-check before calling.

        Args:
            contact_name: Name of the customer or supplier.
            description: Line item description.
            quantity: Quantity of units.
            unit_amount: Price per unit in AUD.
            account_code: Xero account code (default "200" = Sales).
            invoice_type: ACCREC (sales invoice) or ACCPAY (bill). Default ACCREC.
        """
        logger.info("tool.create_invoice", contact=contact_name, amount=unit_amount * quantity)
        invoice_data = {
            "Type": invoice_type,
            "Contact": {"Name": contact_name},
            "LineItems": [
                {
                    "Description": description,
                    "Quantity": quantity,
                    "UnitAmount": unit_amount,
                    "AccountCode": account_code,
                }
            ],
            "Status": "DRAFT",
        }
        result = await client.create_invoice(invoice_data)
        return json.dumps(result, indent=2)
