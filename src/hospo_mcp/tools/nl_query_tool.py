"""Natural language → POS query tool for hospo-mcp.

Lets operators (and AI agents) ask plain English questions about their
Lightspeed O-Series POS data without needing to know the API.

Examples:
  "What were our top 10 items by revenue last Saturday night?"
  "Compare this week's food vs beverage split to last week"
  "Which staff member had the highest average transaction value this month?"
  "What time did we peak on Friday and what were we selling?"
  "Show me items with declining sales over the last 4 weeks"
"""

import json
import re
from datetime import date, datetime, timedelta
from typing import Any, Optional
from mcp.server.fastmcp import FastMCP
from ..clients.lightspeed import LightspeedClient, MOCK_ORDERS, MOCK_CATEGORIES, MOCK_SUMMARY
import structlog

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Date range resolver — maps natural language to ISO date strings
# ---------------------------------------------------------------------------

def _resolve_date_range(query: str) -> tuple[str, str, str]:
    """
    Parse natural language time references into (date_from, date_to, period_label).

    Returns ISO date strings (YYYY-MM-DD) and a human-readable label.
    """
    today = date.today()
    q = query.lower()

    # --- Specific day references ---
    if "yesterday" in q:
        d = today - timedelta(days=1)
        return str(d), str(d), "yesterday"

    if "today" in q:
        return str(today), str(today), "today"

    # "last saturday", "last friday", etc.
    day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for i, name in enumerate(day_names):
        pattern = rf"last\s+{name}|this\s+past\s+{name}"
        if re.search(pattern, q):
            days_back = (today.weekday() - i) % 7
            if days_back == 0:
                days_back = 7  # "last X" means the previous occurrence
            target = today - timedelta(days=days_back)
            return str(target), str(target), f"last {name.capitalize()}"

    # "this week"
    if "this week" in q:
        start = today - timedelta(days=today.weekday())  # Monday
        return str(start), str(today), "this week"

    # "last week"
    if "last week" in q:
        start = today - timedelta(days=today.weekday() + 7)
        end = start + timedelta(days=6)
        return str(start), str(end), "last week"

    # "this month"
    if "this month" in q:
        start = today.replace(day=1)
        return str(start), str(today), "this month"

    # "last month"
    if "last month" in q:
        first_of_this = today.replace(day=1)
        last_day_prev = first_of_this - timedelta(days=1)
        start = last_day_prev.replace(day=1)
        return str(start), str(last_day_prev), "last month"

    # "last N days"
    m = re.search(r"last\s+(\d+)\s+days?", q)
    if m:
        n = int(m.group(1))
        start = today - timedelta(days=n - 1)
        return str(start), str(today), f"last {n} days"

    # "last N weeks"
    m = re.search(r"last\s+(\d+)\s+weeks?", q)
    if m:
        n = int(m.group(1))
        start = today - timedelta(weeks=n)
        return str(start), str(today), f"last {n} weeks"

    # Default: today
    return str(today), str(today), "today"


# ---------------------------------------------------------------------------
# Query intent classifier
# ---------------------------------------------------------------------------

def _classify_intent(query: str) -> str:
    """
    Classify the query intent into one of:
      top_items     — top items by revenue/quantity/margin
      category      — food vs beverage / category breakdown
      staff         — staff performance
      trend         — comparison / trend over time
      peak_time     — peak trading period / hourly breakdown
      summary       — general sales summary / total revenue
    """
    q = query.lower()

    # Staff / employee
    if any(w in q for w in ["staff", "employee", "server", "waiter", "bartender",
                              "who sold", "by staff", "per staff"]):
        return "staff"

    # Peak time / hourly
    if any(w in q for w in ["peak", "busiest", "quiet", "hour", "time", "when did",
                              "what time", "hourly", "rush"]):
        return "peak_time"

    # Category breakdown — check before trend so "food vs beverage" hits here
    if any(w in q for w in ["food", "beverage", "drink", "category", "categories",
                              "split", "breakdown", "beer", "wine", "spirits"]):
        return "category"

    # Trend / comparison
    if any(w in q for w in ["vs ", "versus", "compared to", "compare", "trend",
                              "declining", "growing", "change", "week on week",
                              "last week vs", "vs last"]):
        return "trend"

    # Top items
    if any(w in q for w in ["top", "best", "most popular", "highest", "ranking",
                              "best-selling", "bestselling", "revenue", "quantity",
                              "items", "products", "menu"]):
        return "top_items"

    # Default: summary
    return "summary"


# ---------------------------------------------------------------------------
# Data processors — turn raw mock/API data into insights
# ---------------------------------------------------------------------------

def _extract_top_items(orders: list[dict], limit: int = 10, sort_by: str = "revenue") -> list[dict]:
    """Aggregate order lines into item-level totals, sorted by revenue or quantity."""
    item_totals: dict[str, dict] = {}
    for order in orders:
        for line in order.get("lines", []):
            name = line.get("name", "Unknown")
            if name not in item_totals:
                item_totals[name] = {
                    "name": name,
                    "category": line.get("category", "Unknown"),
                    "revenue": 0.0,
                    "quantity": 0,
                    "orders": 0,
                }
            item_totals[name]["revenue"] += line.get("total", 0)
            item_totals[name]["quantity"] += line.get("quantity", 0)
            item_totals[name]["orders"] += 1

    items = list(item_totals.values())
    sort_key = "quantity" if sort_by == "quantity" else "revenue"
    items.sort(key=lambda x: x[sort_key], reverse=True)
    return items[:limit]


def _extract_category_breakdown(orders: list[dict]) -> dict[str, dict]:
    """Summarise revenue and quantity by category across all orders."""
    categories: dict[str, dict] = {}
    total_revenue = 0.0
    for order in orders:
        for line in order.get("lines", []):
            cat = line.get("category", "Unknown")
            rev = line.get("total", 0)
            qty = line.get("quantity", 0)
            if cat not in categories:
                categories[cat] = {"category": cat, "revenue": 0.0, "quantity": 0}
            categories[cat]["revenue"] += rev
            categories[cat]["quantity"] += qty
            total_revenue += rev

    # Add percentage
    for cat in categories.values():
        cat["revenue_pct"] = round(cat["revenue"] / total_revenue * 100, 1) if total_revenue else 0.0

    return dict(sorted(categories.items(), key=lambda x: x[1]["revenue"], reverse=True))


def _extract_staff_performance(orders: list[dict]) -> list[dict]:
    """Summarise performance by staff_id."""
    staff_stats: dict[str, dict] = {}

    # Mock staff names
    staff_names = {
        "staff_001": "Ren Law",
        "staff_002": "Bek Lemon",
        "staff_003": "Jordan McLean",
    }

    for order in orders:
        sid = order.get("staff_id", "unknown")
        total = order.get("total", 0)
        if sid not in staff_stats:
            staff_stats[sid] = {
                "staff_id": sid,
                "name": staff_names.get(sid, sid),
                "total_revenue": 0.0,
                "order_count": 0,
                "avg_transaction": 0.0,
            }
        staff_stats[sid]["total_revenue"] += total
        staff_stats[sid]["order_count"] += 1

    # Calculate averages
    for s in staff_stats.values():
        s["avg_transaction"] = round(s["total_revenue"] / s["order_count"], 2) if s["order_count"] else 0.0

    result = list(staff_stats.values())
    result.sort(key=lambda x: x["avg_transaction"], reverse=True)
    return result


def _extract_peak_times(summary: dict) -> list[dict]:
    """Return hourly breakdown sorted by revenue."""
    hourly = summary.get("hourlyBreakdown", {})
    periods = [
        {"hour": hour, "revenue": rev / 100}  # convert cents to dollars
        for hour, rev in hourly.items()
    ]
    periods.sort(key=lambda x: x["revenue"], reverse=True)
    return periods


# ---------------------------------------------------------------------------
# Response formatters — turn data into human-readable summaries
# ---------------------------------------------------------------------------

def _format_top_items(items: list[dict], period: str, sort_by: str = "revenue") -> str:
    if not items:
        return f"No sales data found for {period}."
    metric = "revenue" if sort_by != "quantity" else "quantity"
    lines = [f"🏆 Top {len(items)} items by {metric} — {period}:\n"]
    for i, item in enumerate(items, 1):
        rev = f"${item['revenue']:.2f}"
        qty = f"{item['quantity']} sold"
        lines.append(f"  {i}. {item['name']} ({item['category']}) — {rev} | {qty}")
    return "\n".join(lines)


def _format_category_breakdown(cats: dict, period: str, compare_cats: dict = None) -> str:
    if not cats:
        return f"No category data found for {period}."
    lines = [f"📊 Category breakdown — {period}:\n"]
    for name, data in cats.items():
        rev = f"${data['revenue']:.2f}"
        pct = f"{data['revenue_pct']}%"
        line = f"  • {name}: {rev} ({pct})"
        if compare_cats and name in compare_cats:
            prev_rev = compare_cats[name]["revenue"]
            delta = data["revenue"] - prev_rev
            sign = "▲" if delta >= 0 else "▼"
            line += f"  {sign} ${abs(delta):.2f} vs prior period"
        lines.append(line)

    total = sum(d["revenue"] for d in cats.values())
    food_rev = sum(d["revenue"] for k, d in cats.items() if k == "Food")
    bev_rev = sum(d["revenue"] for k, d in cats.items() if k != "Food" and k != "Dessert")
    if total > 0:
        lines.append(f"\n  Food/Bev split: Food {food_rev/total*100:.0f}% | Bev {bev_rev/total*100:.0f}%")
    return "\n".join(lines)


def _format_staff_performance(staff: list[dict], period: str) -> str:
    if not staff:
        return f"No staff data found for {period}."
    lines = [f"👤 Staff performance — {period}:\n"]
    for i, s in enumerate(staff, 1):
        lines.append(
            f"  {i}. {s['name']} — Avg txn: ${s['avg_transaction']:.2f} | "
            f"Total: ${s['total_revenue']:.2f} | {s['order_count']} orders"
        )
    return "\n".join(lines)


def _format_peak_times(periods: list[dict], period: str) -> str:
    if not periods:
        return f"No hourly data found for {period}."
    peak = periods[0]
    lines = [f"⏰ Peak trading — {period}:\n"]
    lines.append(f"  Peak hour: {peak['hour']} (${peak['revenue']:.2f})\n")
    lines.append("  Hourly breakdown (sorted by revenue):")
    for p in periods[:8]:  # top 8 hours
        bar_len = int(p["revenue"] / max(h["revenue"] for h in periods) * 20)
        bar = "█" * bar_len
        lines.append(f"  {p['hour']}  {bar:<20}  ${p['revenue']:.2f}")
    return "\n".join(lines)


def _format_summary(summary: dict, period: str) -> str:
    total = summary.get("totalSales", {}).get("amount", 0) / 100
    txns = summary.get("totalTransactions", 0)
    avg = summary.get("averageTransaction", {}).get("amount", 0) / 100
    top_cat = summary.get("topCategory", "Unknown")
    lines = [
        f"💰 Sales summary — {period}:\n",
        f"  Total revenue: ${total:,.2f}",
        f"  Transactions: {txns}",
        f"  Average transaction: ${avg:.2f}",
        f"  Top category: {top_cat}",
    ]
    return "\n".join(lines)


def _format_trend(this_cats: dict, last_cats: dict, period: str, prev_period: str) -> str:
    """Compare two periods' category breakdowns."""
    all_cats = set(this_cats) | set(last_cats)
    lines = [f"📈 Trend comparison: {period} vs {prev_period}:\n"]
    for cat in sorted(all_cats):
        this_rev = this_cats.get(cat, {}).get("revenue", 0)
        last_rev = last_cats.get(cat, {}).get("revenue", 0)
        delta = this_rev - last_rev
        sign = "▲" if delta >= 0 else "▼"
        lines.append(
            f"  {cat}: ${this_rev:.2f}  ({sign} ${abs(delta):.2f} vs {prev_period})"
        )
    this_total = sum(d["revenue"] for d in this_cats.values())
    last_total = sum(d["revenue"] for d in last_cats.values())
    overall = this_total - last_total
    sign = "▲" if overall >= 0 else "▼"
    lines.append(f"\n  Overall: ${this_total:.2f}  ({sign} ${abs(overall):.2f})")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Core NL query processor
# ---------------------------------------------------------------------------

async def process_nl_query(query: str, client: LightspeedClient) -> dict:
    """
    Translate a natural language query into Lightspeed API calls and return
    structured + human-readable results.

    Returns:
        {
            "query": original query string,
            "interpretation": what the system understood,
            "data": raw structured results,
            "summary": human-readable answer,
        }
    """
    intent = _classify_intent(query)
    date_from, date_to, period_label = _resolve_date_range(query)

    # Determine sort preference for top_items
    q = query.lower()
    sort_by = "quantity" if any(w in q for w in ["quantity", "most sold", "units", "count"]) else "revenue"

    # Parse top N (default 10)
    limit_match = re.search(r"top\s+(\d+)", q)
    top_limit = int(limit_match.group(1)) if limit_match else 10

    interpretation = {
        "intent": intent,
        "period": period_label,
        "date_from": date_from,
        "date_to": date_to,
        "sort_by": sort_by if intent == "top_items" else None,
        "top_limit": top_limit if intent == "top_items" else None,
    }

    data: dict[str, Any] = {}
    summary_text = ""

    try:
        if intent == "top_items":
            orders_result = await client.get_sales(date_from=date_from, date_to=date_to, limit=200)
            orders = orders_result.get("orders", [])
            top_items = _extract_top_items(orders, limit=top_limit, sort_by=sort_by)
            data = {"top_items": top_items, "total_orders": len(orders)}
            summary_text = _format_top_items(top_items, period_label, sort_by)

        elif intent == "category":
            orders_result = await client.get_sales(date_from=date_from, date_to=date_to, limit=200)
            orders = orders_result.get("orders", [])
            cats = _extract_category_breakdown(orders)
            data = {"categories": cats}
            summary_text = _format_category_breakdown(cats, period_label)

        elif intent == "staff":
            orders_result = await client.get_sales(date_from=date_from, date_to=date_to, limit=200)
            orders = orders_result.get("orders", [])
            staff = _extract_staff_performance(orders)
            data = {"staff": staff}
            summary_text = _format_staff_performance(staff, period_label)

        elif intent == "trend":
            # Current period + previous equivalent period
            orders_result = await client.get_sales(date_from=date_from, date_to=date_to, limit=200)
            orders = orders_result.get("orders", [])
            this_cats = _extract_category_breakdown(orders)

            # Calculate previous period of same length
            period_days = (
                datetime.strptime(date_to, "%Y-%m-%d") -
                datetime.strptime(date_from, "%Y-%m-%d")
            ).days + 1
            prev_to = datetime.strptime(date_from, "%Y-%m-%d") - timedelta(days=1)
            prev_from = prev_to - timedelta(days=period_days - 1)
            prev_from_str = prev_from.strftime("%Y-%m-%d")
            prev_to_str = prev_to.strftime("%Y-%m-%d")
            prev_label = f"prior {period_days}-day period"

            prev_orders_result = await client.get_sales(
                date_from=prev_from_str, date_to=prev_to_str, limit=200
            )
            prev_orders = prev_orders_result.get("orders", [])
            prev_cats = _extract_category_breakdown(prev_orders)

            data = {
                "current": this_cats,
                "previous": prev_cats,
                "current_period": period_label,
                "previous_period": prev_label,
            }
            summary_text = _format_trend(this_cats, prev_cats, period_label, prev_label)

        elif intent == "peak_time":
            sales_summary = await client.get_sales_summary(date=date_from)
            peak_times = _extract_peak_times(sales_summary)
            data = {"hourly_breakdown": peak_times, "summary": sales_summary}
            summary_text = _format_peak_times(peak_times, period_label)

        else:  # summary
            sales_summary = await client.get_sales_summary(date=date_from)
            data = {"summary": sales_summary}
            summary_text = _format_summary(sales_summary, period_label)

    except Exception as exc:
        logger.error("nl_query.error", query=query, intent=intent, error=str(exc))
        data = {"error": str(exc)}
        summary_text = f"Sorry, I couldn't process that query: {exc}"

    return {
        "query": query,
        "interpretation": interpretation,
        "data": data,
        "summary": summary_text,
    }


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------

def register_nl_query_tool(mcp: FastMCP, client: LightspeedClient):
    """Register the nl_pos_query tool with the MCP server."""

    @mcp.tool()
    async def nl_pos_query(query: str) -> str:
        """
        Ask any question about your POS data in plain English.

        This tool translates natural language into Lightspeed O-Series API calls
        and returns a structured + human-readable answer. No API knowledge required.

        Supported query types:
        - Top items: "What were our top 10 items by revenue last Saturday?"
        - Category breakdown: "Show me the food vs beverage split this week"
        - Staff performance: "Which staff had the highest average transaction this month?"
        - Trend comparison: "How did this week compare to last week?"
        - Peak time: "What was our busiest hour yesterday?"
        - Sales summary: "What were total sales today?"

        Args:
            query: Plain English question about your POS data.

        Returns:
            JSON with keys:
              - query: the original question
              - interpretation: what the system understood (intent, date range)
              - data: structured results
              - summary: human-readable answer
        """
        logger.info("tool.nl_pos_query", query=query)
        result = await process_nl_query(query, client)
        return json.dumps(result, indent=2, default=str)
