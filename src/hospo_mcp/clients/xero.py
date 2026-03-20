"""Xero accounting client — wraps Xero API v2."""

from datetime import date, datetime, timedelta
from typing import Any, Optional
from .base import BaseClient
from ..config import XeroConfig
import structlog

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

MOCK_ACCOUNTS = [
    {"AccountID": "acc_001", "Code": "200", "Name": "Sales - Food", "Type": "REVENUE", "Balance": 48200.50},
    {"AccountID": "acc_002", "Code": "201", "Name": "Sales - Beverage", "Type": "REVENUE", "Balance": 62100.00},
    {"AccountID": "acc_003", "Code": "400", "Name": "Cost of Goods Sold", "Type": "DIRECTCOSTS", "Balance": 28400.75},
    {"AccountID": "acc_004", "Code": "461", "Name": "Wages & Salaries", "Type": "OVERHEADS", "Balance": 41200.00},
    {"AccountID": "acc_005", "Code": "462", "Name": "Superannuation", "Type": "OVERHEADS", "Balance": 3908.00},
    {"AccountID": "acc_006", "Code": "480", "Name": "Rent", "Type": "OVERHEADS", "Balance": 8500.00},
    {"AccountID": "acc_007", "Code": "481", "Name": "Utilities", "Type": "OVERHEADS", "Balance": 2340.00},
    {"AccountID": "acc_008", "Code": "800", "Name": "GST", "Type": "LIABILITY", "Balance": 8420.00},
]

MOCK_INVOICES = [
    {
        "InvoiceID": "inv_001",
        "InvoiceNumber": "INV-1045",
        "Type": "ACCREC",
        "Status": "AUTHORISED",
        "Contact": {"Name": "Coopers Brewery"},
        "AmountDue": 4800.00,
        "AmountPaid": 0,
        "DueDate": "2024-04-05",
        "Date": "2024-03-20",
        "CurrencyCode": "AUD",
        "LineItems": [
            {"Description": "Draught beer supply - March", "Quantity": 4, "UnitAmount": 1200.00}
        ],
    },
    {
        "InvoiceID": "inv_002",
        "InvoiceNumber": "INV-1046",
        "Type": "ACCREC",
        "Status": "PAID",
        "Contact": {"Name": "Sysco Foods"},
        "AmountDue": 0,
        "AmountPaid": 2340.50,
        "DueDate": "2024-03-25",
        "Date": "2024-03-18",
        "CurrencyCode": "AUD",
        "LineItems": [
            {"Description": "Weekly food supply", "Quantity": 1, "UnitAmount": 2340.50}
        ],
    },
    {
        "InvoiceID": "inv_003",
        "InvoiceNumber": "BILL-0022",
        "Type": "ACCPAY",
        "Status": "AUTHORISED",
        "Contact": {"Name": "AGL Energy"},
        "AmountDue": 1240.00,
        "AmountPaid": 0,
        "DueDate": "2024-04-10",
        "Date": "2024-03-15",
        "CurrencyCode": "AUD",
    },
]

MOCK_PROFIT_LOSS = {
    "reportName": "Profit and Loss",
    "fromDate": "2024-03-01",
    "toDate": "2024-03-31",
    "currency": "AUD",
    "revenue": {
        "Food Sales": 48200.50,
        "Beverage Sales": 62100.00,
        "Total Revenue": 110300.50,
    },
    "costOfGoods": {
        "Food Cost": 14460.15,
        "Beverage Cost": 13946.60,
        "Total COGS": 28406.75,
    },
    "grossProfit": 81893.75,
    "grossMargin": "74.2%",
    "expenses": {
        "Wages & Salaries": 41200.00,
        "Superannuation": 3908.00,
        "Rent": 8500.00,
        "Utilities": 2340.00,
        "Marketing": 1200.00,
        "Insurance": 650.00,
        "Total Expenses": 57798.00,
    },
    "netProfit": 24095.75,
    "netMargin": "21.8%",
}

MOCK_CASH_FLOW = {
    "period": "2024-03-01 to 2024-03-31",
    "openingBalance": 18400.00,
    "receipts": 110300.50,
    "payments": 86204.75,
    "closingBalance": 42495.75,
    "currency": "AUD",
}

MOCK_CONTACTS = [
    {"ContactID": "con_001", "Name": "Coopers Brewery", "EmailAddress": "orders@coopers.com.au", "IsSupplier": True},
    {"ContactID": "con_002", "Name": "Sysco Foods", "EmailAddress": "accounts@sysco.com.au", "IsSupplier": True},
    {"ContactID": "con_003", "Name": "AGL Energy", "EmailAddress": "business@agl.com.au", "IsSupplier": True},
    {"ContactID": "con_004", "Name": "Lion Co", "EmailAddress": "draught@lionco.com.au", "IsSupplier": True},
]


class XeroClient(BaseClient):
    """Client for Xero accounting API."""

    def __init__(self, cfg: XeroConfig, use_mock: bool = True):
        super().__init__(
            base_url=cfg.base_url,
            token=cfg.access_token,
            use_mock=use_mock or not cfg.configured,
        )
        self.tenant_id = cfg.tenant_id or "MOCK_TENANT"

    def _auth_headers(self) -> dict:
        return {"Xero-Tenant-Id": self.tenant_id}

    async def get_accounts(self) -> dict:
        """Get chart of accounts."""
        return await self.get("/Accounts", {})

    async def get_invoices(
        self,
        status: Optional[str] = None,
        invoice_type: Optional[str] = None,
        date_from: Optional[str] = None,
    ) -> dict:
        """Get invoices and bills."""
        params = {}
        if status:
            params["Statuses"] = status
        if invoice_type:
            params["Type"] = invoice_type
        return await self.get("/Invoices", params)

    async def get_profit_loss(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> dict:
        """Get P&L report."""
        params = {"fromDate": from_date or "", "toDate": to_date or ""}
        return await self.get("/Reports/ProfitAndLoss", params)

    async def get_cash_flow(self) -> dict:
        """Get cash flow summary."""
        return await self.get("/Reports/CashSummary", {})

    async def get_contacts(self, is_supplier: Optional[bool] = None) -> dict:
        """Get contacts (suppliers/customers)."""
        params = {}
        if is_supplier is not None:
            params["IsSupplier"] = str(is_supplier).upper()
        return await self.get("/Contacts", params)

    async def create_invoice(self, invoice_data: dict) -> dict:
        """Create a new invoice or bill."""
        return await self.post("/Invoices", invoice_data)

    async def get_gst_summary(self) -> dict:
        """Get GST/BAS summary."""
        return await self.get("/Reports/BASReport", {})

    # ------------------------------------------------------------------
    # Mock overrides
    # ------------------------------------------------------------------

    async def _mock_get(self, path: str, params: dict) -> dict:
        if "/Accounts" in path:
            return {"Accounts": MOCK_ACCOUNTS, "total": len(MOCK_ACCOUNTS), "mock": True}
        if "/Invoices" in path:
            invoices = MOCK_INVOICES
            if params.get("Type"):
                invoices = [i for i in invoices if i["Type"] == params["Type"]]
            if params.get("Statuses"):
                invoices = [i for i in invoices if i["Status"] == params["Statuses"]]
            return {"Invoices": invoices, "total": len(invoices), "mock": True}
        if "ProfitAndLoss" in path:
            return {**MOCK_PROFIT_LOSS, "mock": True}
        if "CashSummary" in path:
            return {**MOCK_CASH_FLOW, "mock": True}
        if "/Contacts" in path:
            return {"Contacts": MOCK_CONTACTS, "total": len(MOCK_CONTACTS), "mock": True}
        if "BASReport" in path:
            return {
                "gstOnSales": 10027.32,
                "gstOnPurchases": 2582.43,
                "netGST": 7444.89,
                "period": "March 2024",
                "mock": True,
            }
        return {"mock": True, "path": path}

    async def _mock_post(self, path: str, data: dict) -> dict:
        import uuid
        return {
            "mock": True,
            "InvoiceID": str(uuid.uuid4()),
            "Status": "DRAFT",
            "InvoiceNumber": f"INV-{1050}",
            "message": "Invoice created (mock)",
        }
