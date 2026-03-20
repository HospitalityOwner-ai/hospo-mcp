"""Tests for API clients in mock mode."""

import pytest
from hospo_mcp.clients.lightspeed import LightspeedClient
from hospo_mcp.clients.xero import XeroClient
from hospo_mcp.clients.deputy import DeputyClient
from hospo_mcp.config import LightspeedConfig, XeroConfig, DeputyConfig


@pytest.fixture
def lightspeed():
    return LightspeedClient(LightspeedConfig(), use_mock=True)


@pytest.fixture
def xero():
    return XeroClient(XeroConfig(), use_mock=True)


@pytest.fixture
def deputy():
    return DeputyClient(DeputyConfig(), use_mock=True)


# ── Lightspeed O-Series (Kounta) ──────────────────────────────────────────────

class TestLightspeedClient:
    async def test_get_sales_returns_mock_data(self, lightspeed):
        result = await lightspeed.get_sales()
        assert "orders" in result
        assert isinstance(result["orders"], list)
        assert len(result["orders"]) > 0
        assert result["mock"] is True

    async def test_get_sales_summary(self, lightspeed):
        result = await lightspeed.get_sales_summary()
        assert "totalSales" in result
        assert "totalTransactions" in result
        assert "hourlyBreakdown" in result

    async def test_get_items(self, lightspeed):
        result = await lightspeed.get_items()
        assert "products" in result
        assert len(result["products"]) > 0

    async def test_get_items_filtered_by_category(self, lightspeed):
        result = await lightspeed.get_items(category="Food")
        for item in result["products"]:
            assert item["category"] == "Food"

    async def test_get_categories(self, lightspeed):
        result = await lightspeed.get_categories()
        assert "categories" in result
        assert len(result["categories"]) > 0

    async def test_get_sites(self, lightspeed):
        result = await lightspeed.get_sites()
        assert "sites" in result
        assert len(result["sites"]) > 0
        # Each site should have an id and name
        for site in result["sites"]:
            assert "id" in site
            assert "name" in site

    async def test_get_company(self, lightspeed):
        result = await lightspeed.get_company()
        assert "name" in result
        assert result["mock"] is True

    async def test_update_item_price(self, lightspeed):
        result = await lightspeed.update_item_price("prod_001", 2600)
        assert result["updated"] is True
        assert result["mock"] is True

    async def test_get_item_by_id(self, lightspeed):
        result = await lightspeed.get_item_by_id("prod_001")
        assert "product" in result
        assert result["mock"] is True

    async def test_site_id_defaults_to_mock(self, lightspeed):
        # site_id should fall back gracefully with no config
        assert lightspeed.site_id == "MOCK_SITE"

    async def test_config_uses_site_id_not_account_id(self):
        cfg = LightspeedConfig()
        # O-Series uses site_id; account_id should not exist
        assert hasattr(cfg, "site_id")
        assert not hasattr(cfg, "account_id")

    async def test_base_url_is_kounta(self, lightspeed):
        assert "kounta.com" in lightspeed.base_url


# ── Xero ──────────────────────────────────────────────────────────────────────

class TestXeroClient:
    async def test_get_accounts(self, xero):
        result = await xero.get_accounts()
        assert "Accounts" in result
        assert len(result["Accounts"]) > 0

    async def test_get_invoices(self, xero):
        result = await xero.get_invoices()
        assert "Invoices" in result
        assert len(result["Invoices"]) > 0

    async def test_get_invoices_filtered_by_type(self, xero):
        result = await xero.get_invoices(invoice_type="ACCREC")
        for inv in result["Invoices"]:
            assert inv["Type"] == "ACCREC"

    async def test_get_profit_loss(self, xero):
        result = await xero.get_profit_loss()
        assert "revenue" in result
        assert "netProfit" in result
        assert result["mock"] is True

    async def test_get_cash_flow(self, xero):
        result = await xero.get_cash_flow()
        assert "openingBalance" in result
        assert "closingBalance" in result

    async def test_get_suppliers(self, xero):
        result = await xero.get_contacts(is_supplier=True)
        assert "Contacts" in result

    async def test_get_gst_summary(self, xero):
        result = await xero.get_gst_summary()
        assert "gstOnSales" in result
        assert "netGST" in result

    async def test_create_invoice(self, xero):
        result = await xero.create_invoice({
            "Type": "ACCREC",
            "Contact": {"Name": "Test Customer"},
            "LineItems": [{"Description": "Test", "Quantity": 1, "UnitAmount": 100.0}],
        })
        assert result["mock"] is True
        assert "InvoiceID" in result


# ── Deputy ────────────────────────────────────────────────────────────────────

class TestDeputyClient:
    async def test_get_employees(self, deputy):
        result = await deputy.get_employees()
        assert "Employees" in result
        assert len(result["Employees"]) > 0

    async def test_get_employees_active_only(self, deputy):
        result = await deputy.get_employees(active_only=True)
        for emp in result["Employees"]:
            assert emp["Active"] is True

    async def test_get_rosters(self, deputy):
        result = await deputy.get_rosters()
        assert "Rosters" in result
        assert len(result["Rosters"]) > 0

    async def test_get_timesheets(self, deputy):
        result = await deputy.get_timesheets()
        assert "Timesheets" in result

    async def test_get_pending_timesheets(self, deputy):
        result = await deputy.get_timesheets(status="PENDING")
        for ts in result["Timesheets"]:
            assert ts["Status"] == "PENDING"

    async def test_get_labour_cost(self, deputy):
        result = await deputy.get_labour_cost()
        assert "totalCost" in result
        assert "labourCostPercentage" in result

    async def test_get_leave_requests(self, deputy):
        result = await deputy.get_leave_requests()
        assert "Leave" in result

    async def test_approve_leave(self, deputy):
        result = await deputy.approve_leave(301)
        assert result["approved"] is True

    async def test_create_roster(self, deputy):
        result = await deputy.create_roster({
            "EmployeeId": 1,
            "Area": "FOH",
            "StartTime": "2024-03-23T17:00:00",
            "EndTime": "2024-03-23T23:00:00",
        })
        assert result["created"] is True
