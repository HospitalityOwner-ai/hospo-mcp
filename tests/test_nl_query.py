"""Tests for the natural language → POS query tool."""

import pytest
from datetime import date, timedelta
from hospo_mcp.clients.lightspeed import LightspeedClient
from hospo_mcp.config import LightspeedConfig
from hospo_mcp.tools.nl_query_tool import (
    process_nl_query,
    _classify_intent,
    _resolve_date_range,
    _extract_top_items,
    _extract_category_breakdown,
    _extract_staff_performance,
    _extract_peak_times,
    MOCK_ORDERS,
)
from hospo_mcp.clients.lightspeed import MOCK_SUMMARY


@pytest.fixture
def lightspeed():
    return LightspeedClient(LightspeedConfig(), use_mock=True)


# ---------------------------------------------------------------------------
# Unit: intent classifier
# ---------------------------------------------------------------------------

class TestIntentClassifier:
    def test_top_items_intent(self):
        assert _classify_intent("What were our top 10 items by revenue?") == "top_items"
        assert _classify_intent("best selling products this week") == "top_items"
        assert _classify_intent("highest revenue items last month") == "top_items"

    def test_category_intent(self):
        assert _classify_intent("show me the food vs beverage split") == "category"
        assert _classify_intent("category breakdown for today") == "category"
        assert _classify_intent("how much beer did we sell?") == "category"

    def test_staff_intent(self):
        assert _classify_intent("which staff member had the highest average transaction?") == "staff"
        assert _classify_intent("employee performance this week") == "staff"
        assert _classify_intent("who sold the most today?") == "staff"

    def test_trend_intent(self):
        assert _classify_intent("compare this week to last week") == "trend"
        assert _classify_intent("how did we do vs last week?") == "trend"
        assert _classify_intent("sales trend over the last 4 weeks") == "trend"

    def test_peak_time_intent(self):
        assert _classify_intent("when was our busiest hour yesterday?") == "peak_time"
        assert _classify_intent("what time did we peak on Friday?") == "peak_time"
        assert _classify_intent("hourly breakdown for today") == "peak_time"

    def test_summary_intent_default(self):
        assert _classify_intent("what were total sales today?") == "summary"
        assert _classify_intent("how did we do yesterday?") == "summary"


# ---------------------------------------------------------------------------
# Unit: date range resolver
# ---------------------------------------------------------------------------

class TestDateRangeResolver:
    def test_today(self):
        d_from, d_to, label = _resolve_date_range("what were sales today?")
        today = str(date.today())
        assert d_from == today
        assert d_to == today
        assert "today" in label

    def test_yesterday(self):
        d_from, d_to, label = _resolve_date_range("show me yesterday's numbers")
        yesterday = str(date.today() - timedelta(days=1))
        assert d_from == yesterday
        assert d_to == yesterday
        assert "yesterday" in label

    def test_this_week(self):
        d_from, d_to, label = _resolve_date_range("sales this week")
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        assert d_from == str(monday)
        assert d_to == str(today)
        assert "week" in label

    def test_last_week(self):
        d_from, d_to, label = _resolve_date_range("how did last week go?")
        today = date.today()
        start = today - timedelta(days=today.weekday() + 7)
        end = start + timedelta(days=6)
        assert d_from == str(start)
        assert d_to == str(end)
        assert "last week" in label

    def test_last_n_days(self):
        d_from, d_to, label = _resolve_date_range("sales over the last 7 days")
        today = date.today()
        start = today - timedelta(days=6)
        assert d_from == str(start)
        assert d_to == str(today)
        assert "7" in label

    def test_this_month(self):
        d_from, d_to, label = _resolve_date_range("revenue this month")
        today = date.today()
        first = today.replace(day=1)
        assert d_from == str(first)
        assert d_to == str(today)
        assert "month" in label

    def test_last_saturday(self):
        d_from, d_to, label = _resolve_date_range("top items last Saturday night")
        assert "Saturday" in label
        # Should be a valid date within the past 7 days
        target = date.fromisoformat(d_from)
        assert target.weekday() == 5  # Saturday = 5
        assert (date.today() - target).days <= 7


# ---------------------------------------------------------------------------
# Unit: data processors
# ---------------------------------------------------------------------------

class TestDataProcessors:
    def test_extract_top_items_by_revenue(self):
        items = _extract_top_items(MOCK_ORDERS, limit=5, sort_by="revenue")
        assert len(items) <= 5
        # Should be sorted descending by revenue
        revenues = [i["revenue"] for i in items]
        assert revenues == sorted(revenues, reverse=True)

    def test_extract_top_items_by_quantity(self):
        items = _extract_top_items(MOCK_ORDERS, limit=5, sort_by="quantity")
        quantities = [i["quantity"] for i in items]
        assert quantities == sorted(quantities, reverse=True)

    def test_extract_top_items_all_fields(self):
        items = _extract_top_items(MOCK_ORDERS)
        for item in items:
            assert "name" in item
            assert "category" in item
            assert "revenue" in item
            assert "quantity" in item

    def test_extract_category_breakdown(self):
        cats = _extract_category_breakdown(MOCK_ORDERS)
        assert len(cats) > 0
        # Food should exist
        assert "Food" in cats
        # All revenue_pct should sum to ~100
        total_pct = sum(c["revenue_pct"] for c in cats.values())
        assert abs(total_pct - 100.0) < 0.5

    def test_extract_staff_performance(self):
        staff = _extract_staff_performance(MOCK_ORDERS)
        assert len(staff) > 0
        for s in staff:
            assert "name" in s
            assert "avg_transaction" in s
            assert "order_count" in s
            assert s["order_count"] > 0

    def test_extract_peak_times(self):
        peaks = _extract_peak_times(MOCK_SUMMARY)
        assert len(peaks) > 0
        revenues = [p["revenue"] for p in peaks]
        assert revenues == sorted(revenues, reverse=True)


# ---------------------------------------------------------------------------
# Integration: full nl_pos_query flow (5 query types)
# ---------------------------------------------------------------------------

class TestNLQueryIntegration:
    """End-to-end tests using the mock LightspeedClient."""

    async def test_top_items_query(self, lightspeed):
        """Query type 1: top items by revenue."""
        result = await process_nl_query(
            "What were our top 10 items by revenue last Saturday night?",
            lightspeed,
        )
        assert result["query"].startswith("What were")
        assert result["interpretation"]["intent"] == "top_items"
        assert result["interpretation"]["top_limit"] == 10
        assert "Saturday" in result["interpretation"]["period"]
        assert "top_items" in result["data"]
        assert len(result["data"]["top_items"]) > 0
        assert "Top" in result["summary"]

    async def test_category_breakdown_query(self, lightspeed):
        """Query type 2: food vs beverage split."""
        result = await process_nl_query(
            "Show me the food vs beverage split this week",
            lightspeed,
        )
        assert result["interpretation"]["intent"] == "category"
        assert "this week" in result["interpretation"]["period"]
        assert "categories" in result["data"]
        assert "Food" in result["data"]["categories"]
        assert "Category breakdown" in result["summary"]

    async def test_staff_performance_query(self, lightspeed):
        """Query type 3: staff performance."""
        result = await process_nl_query(
            "Which staff member had the highest average transaction value this month?",
            lightspeed,
        )
        assert result["interpretation"]["intent"] == "staff"
        assert "staff" in result["data"]
        staff_list = result["data"]["staff"]
        assert len(staff_list) > 0
        # Should be sorted by avg_transaction descending
        avgs = [s["avg_transaction"] for s in staff_list]
        assert avgs == sorted(avgs, reverse=True)
        assert "Staff performance" in result["summary"]

    async def test_trend_comparison_query(self, lightspeed):
        """Query type 4: trend/comparison."""
        result = await process_nl_query(
            "Compare this week's sales to last week",
            lightspeed,
        )
        assert result["interpretation"]["intent"] == "trend"
        assert "current" in result["data"]
        assert "previous" in result["data"]
        assert "Trend comparison" in result["summary"]

    async def test_peak_time_query(self, lightspeed):
        """Query type 5: peak trading time."""
        result = await process_nl_query(
            "What was our busiest hour yesterday?",
            lightspeed,
        )
        assert result["interpretation"]["intent"] == "peak_time"
        assert "hourly_breakdown" in result["data"]
        assert len(result["data"]["hourly_breakdown"]) > 0
        assert "Peak trading" in result["summary"]

    async def test_sales_summary_query(self, lightspeed):
        """Query type 6: general summary."""
        result = await process_nl_query(
            "What were total sales today?",
            lightspeed,
        )
        assert result["interpretation"]["intent"] == "summary"
        assert "summary" in result["data"]
        assert "Sales summary" in result["summary"]

    async def test_result_structure(self, lightspeed):
        """All queries must return the 4-key standard structure."""
        result = await process_nl_query("top 5 items this week", lightspeed)
        assert "query" in result
        assert "interpretation" in result
        assert "data" in result
        assert "summary" in result
        assert result["query"] == "top 5 items this week"

    async def test_interpretation_has_required_fields(self, lightspeed):
        """Interpretation block should always have intent, period, date_from, date_to."""
        result = await process_nl_query("how did we do yesterday?", lightspeed)
        interp = result["interpretation"]
        assert "intent" in interp
        assert "period" in interp
        assert "date_from" in interp
        assert "date_to" in interp

    async def test_mock_mode_works_without_credentials(self):
        """Tool must work in mock mode — no credentials required."""
        fresh_client = LightspeedClient(LightspeedConfig(), use_mock=True)
        result = await process_nl_query(
            "What were our top items by revenue today?",
            fresh_client,
        )
        assert result is not None
        assert result["data"] is not None
        assert len(result["summary"]) > 0

    async def test_quantity_sort(self, lightspeed):
        """Sort by quantity when query asks for most sold."""
        result = await process_nl_query(
            "What were the most sold items by quantity this week?",
            lightspeed,
        )
        assert result["interpretation"]["sort_by"] == "quantity"
        items = result["data"]["top_items"]
        quantities = [i["quantity"] for i in items]
        assert quantities == sorted(quantities, reverse=True)
