"""
Pre-built MCP prompts for common hospo workflows.

These give AI agents a head-start on common tasks without needing
to construct the analysis from scratch.
"""

from mcp.server.fastmcp import FastMCP


def register_prompts(mcp: FastMCP):
    """Register MCP prompts."""

    @mcp.prompt()
    def eod_report() -> str:
        """
        End-of-day report prompt.

        Asks the AI to compile a complete end-of-day business summary
        using all available data from POS, financials, and staff systems.
        """
        return """
You are a hospitality business analyst. Using the available tools, compile a complete
end-of-day report for the venue operator. Include:

1. **Sales Summary** — call get_sales_summary to get today's totals
2. **Top Categories** — call get_sales_categories for category breakdown
3. **Labour Cost** — call get_labour_cost and calculate labour % of today's revenue
4. **Pending Approvals** — call get_pending_timesheets and get_leave_requests(status="PENDING")
5. **Outstanding Invoices** — call get_outstanding_invoices from Xero

Format the report as a clear, concise brief that a busy venue owner can read in 2 minutes.
Lead with the headline numbers, flag anything that needs attention.
""".strip()

    @mcp.prompt()
    def weekly_financial_review() -> str:
        """
        Weekly financial review prompt.

        Guides the AI through a weekly financial health check
        across P&L, cash flow, labour costs, and GST position.
        """
        return """
You are a hospitality CFO. Conduct a weekly financial review using the available tools:

1. **P&L** — call get_profit_and_loss for the week's revenue, COGS, and net profit
2. **Cash Flow** — call get_cash_flow for current cash position
3. **GST Position** — call get_gst_summary to check GST liability
4. **Labour Costs** — call get_labour_cost to check labour % vs target (aim for <30%)
5. **Outstanding** — call get_outstanding_invoices for overdue amounts

Highlight:
- Any margin that's off-target (food cost target: <35% of food revenue, beverages: <25%)
- Labour cost vs benchmark
- Cash position and upcoming liabilities
- Actions needed before end of week
""".strip()

    @mcp.prompt()
    def roster_check() -> str:
        """
        Roster check and gap analysis prompt.

        Helps identify coverage gaps, unconfirmed shifts,
        and staff cost optimisation opportunities.
        """
        return """
You are a hospitality operations manager. Review the current roster using:

1. **Today's Roster** — call get_roster to see who's scheduled
2. **Employees** — call get_employees if you need to see available staff
3. **Labour Cost** — call get_labour_cost to check projected labour spend

Identify:
- Any OPEN shifts that haven't been assigned
- Areas that might be under or over-staffed for the expected trade
- Whether the shift mix aligns with the busiest trading hours (typically 6pm-10pm Fri/Sat)
- Recommendations for roster optimisation

Be concise. Flag actions needed (who to call, what to change) clearly.
""".strip()

    @mcp.prompt()
    def price_review() -> str:
        """
        Menu price review prompt.

        Guides the AI through a data-driven menu price analysis
        using sales data and cost information.
        """
        return """
You are a hospitality menu consultant. Analyse the current pricing using:

1. **Menu Items** — call get_menu_items to see current prices
2. **Category Performance** — call get_sales_categories for revenue by category
3. **Sales Detail** — call get_sales for recent transaction data

Look for:
- Items with unusually high or low velocity (bestsellers vs slow movers)
- Price gaps vs typical market rates (burgers $22–28, pints $10–13, glasses of wine $11–16 in AUS)
- Categories underperforming in revenue
- Opportunities to use premium pricing on high-demand items

Provide 3–5 specific, actionable pricing recommendations with expected revenue impact.
""".strip()

    @mcp.prompt()
    def payroll_prep() -> str:
        """
        Payroll preparation prompt.

        Helps process payroll by reviewing timesheets, leave,
        and generating a Xero-ready summary.
        """
        return """
You are a payroll officer preparing for the pay run. Use these tools:

1. **Pending Timesheets** — call get_pending_timesheets to see what needs approval
2. **Leave Requests** — call get_leave_requests(status="PENDING") for pending leave
3. **Approved Timesheets** — call get_timesheets(status="APPROVED") for this pay period
4. **Employees** — call get_employees for rates and details

Summarise:
- Total hours per employee this period
- Total payroll cost
- Any timesheet anomalies (missed clock-ins, overtime, unusual hours)
- Leave to be included in the pay run
- Confirm if payroll is ready to export to Xero or if approvals are outstanding

Format as a payroll processing checklist.
""".strip()
