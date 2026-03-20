"""MCP tools for Deputy workforce management."""

import json
from mcp.server.fastmcp import FastMCP
from ..clients.deputy import DeputyClient
import structlog

logger = structlog.get_logger()


def register_deputy_tools(mcp: FastMCP, client: DeputyClient):
    """Register all Deputy tools with the MCP server."""

    @mcp.tool()
    async def get_employees(active_only: bool = True) -> str:
        """
        Get employees from Deputy.

        Returns employee names, roles, hourly rates, and assigned areas.

        Args:
            active_only: If True (default), only return active employees.
        """
        logger.info("tool.get_employees", active_only=active_only)
        result = await client.get_employees(active_only=active_only)
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def get_roster(
        date_from: str = "",
        date_to: str = "",
    ) -> str:
        """
        Get the staff roster/schedule from Deputy.

        Returns all scheduled shifts with employee names, areas, start/end times,
        and shift status (CONFIRMED, OPEN, etc).

        Args:
            date_from: Start date (YYYY-MM-DD). Defaults to today.
            date_to: End date (YYYY-MM-DD). Defaults to today.
        """
        logger.info("tool.get_roster", date_from=date_from, date_to=date_to)
        result = await client.get_rosters(
            date_from=date_from or None,
            date_to=date_to or None,
        )
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def get_timesheets(
        date_from: str = "",
        date_to: str = "",
        employee_id: int = 0,
        status: str = "",
    ) -> str:
        """
        Get timesheets from Deputy.

        Returns actual hours worked, start/end times, hourly rates, and total costs.
        Useful for payroll processing and labour cost analysis.

        Args:
            date_from: Start date (YYYY-MM-DD). Defaults to today.
            date_to: End date (YYYY-MM-DD). Defaults to today.
            employee_id: Filter by employee ID. 0 = all employees.
            status: Filter by status — PENDING, APPROVED. Leave blank for all.
        """
        logger.info("tool.get_timesheets", date_from=date_from, status=status)
        result = await client.get_timesheets(
            date_from=date_from or None,
            date_to=date_to or None,
            employee_id=employee_id or None,
            status=status or None,
        )
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def get_pending_timesheets() -> str:
        """
        Get all timesheets awaiting approval from Deputy.

        Returns timesheets in PENDING status that need manager sign-off
        before payroll can be processed.
        """
        logger.info("tool.get_pending_timesheets")
        result = await client.get_timesheets(status="PENDING")
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def get_labour_cost(week_start: str = "") -> str:
        """
        Get labour cost analysis from Deputy.

        Returns total hours worked, total cost, labour cost as a % of revenue,
        and a breakdown by area (Kitchen, FOH, Bar, etc).

        Args:
            week_start: Week start date (YYYY-MM-DD, must be a Monday).
                        Defaults to the current week.
        """
        logger.info("tool.get_labour_cost", week_start=week_start)
        result = await client.get_labour_cost(week_start=week_start or None)
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def get_leave_requests(status: str = "") -> str:
        """
        Get leave requests from Deputy.

        Returns all leave requests with employee names, leave type, dates,
        and approval status.

        Args:
            status: Filter by status — PENDING, APPROVED. Leave blank for all.
        """
        logger.info("tool.get_leave_requests", status=status)
        result = await client.get_leave_requests(status=status or None)
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def approve_leave_request(leave_id: int) -> str:
        """
        Approve a leave request in Deputy.

        ⚠️ This writes to Deputy. Double-check before calling.

        Args:
            leave_id: The Deputy leave request ID to approve.
        """
        logger.info("tool.approve_leave_request", leave_id=leave_id)
        result = await client.approve_leave(leave_id)
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def create_roster_shift(
        employee_id: int,
        area: str,
        start_time: str,
        end_time: str,
        date: str,
    ) -> str:
        """
        Create a new roster shift in Deputy.

        ⚠️ This writes to Deputy. Double-check before calling.

        Args:
            employee_id: Deputy employee ID.
            area: Work area (e.g. "Kitchen", "Bar", "FOH").
            start_time: Shift start time (HH:MM, 24h format).
            end_time: Shift end time (HH:MM, 24h format).
            date: Shift date (YYYY-MM-DD).
        """
        logger.info("tool.create_roster_shift", employee_id=employee_id, date=date)
        roster_data = {
            "EmployeeId": employee_id,
            "Area": area,
            "StartTime": f"{date}T{start_time}:00",
            "EndTime": f"{date}T{end_time}:00",
            "Status": "CONFIRMED",
        }
        result = await client.create_roster(roster_data)
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def get_employee(employee_id: int) -> str:
        """
        Get details for a specific employee from Deputy.

        Args:
            employee_id: The Deputy employee ID.
        """
        logger.info("tool.get_employee", employee_id=employee_id)
        result = await client.get_employee_by_id(employee_id)
        return json.dumps(result, indent=2)
