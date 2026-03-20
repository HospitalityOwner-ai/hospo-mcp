"""Deputy workforce management client."""

from datetime import date, datetime, timedelta
from typing import Any, Optional
from .base import BaseClient
from ..config import DeputyConfig
import structlog

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

MOCK_EMPLOYEES = [
    {
        "Id": 1,
        "FirstName": "Sarah",
        "LastName": "Chen",
        "Email": "sarah.chen@venue.com.au",
        "Role": "Venue Manager",
        "HourlyRate": 32.50,
        "Active": True,
        "Areas": ["FOH", "Management"],
    },
    {
        "Id": 2,
        "FirstName": "Liam",
        "LastName": "O'Brien",
        "Email": "liam.obrien@venue.com.au",
        "Role": "Head Chef",
        "HourlyRate": 38.00,
        "Active": True,
        "Areas": ["Kitchen"],
    },
    {
        "Id": 3,
        "FirstName": "Maya",
        "LastName": "Patel",
        "Email": "maya.patel@venue.com.au",
        "Role": "Bar Supervisor",
        "HourlyRate": 29.00,
        "Active": True,
        "Areas": ["Bar", "FOH"],
    },
    {
        "Id": 4,
        "FirstName": "Jake",
        "LastName": "Williams",
        "Email": "jake.williams@venue.com.au",
        "Role": "Wait Staff",
        "HourlyRate": 24.50,
        "Active": True,
        "Areas": ["FOH"],
    },
    {
        "Id": 5,
        "FirstName": "Amelia",
        "LastName": "Torres",
        "Email": "amelia.torres@venue.com.au",
        "Role": "Cook",
        "HourlyRate": 27.00,
        "Active": True,
        "Areas": ["Kitchen"],
    },
    {
        "Id": 6,
        "FirstName": "Connor",
        "LastName": "Nguyen",
        "Email": "connor.nguyen@venue.com.au",
        "Role": "Casual Bartender",
        "HourlyRate": 24.50,
        "Active": True,
        "Areas": ["Bar"],
    },
]

MOCK_ROSTERS = [
    {
        "Id": 101,
        "EmployeeId": 1,
        "Employee": "Sarah Chen",
        "Area": "Management",
        "StartTime": "2024-03-22T10:00:00",
        "EndTime": "2024-03-22T18:00:00",
        "HoursScheduled": 8.0,
        "Status": "CONFIRMED",
    },
    {
        "Id": 102,
        "EmployeeId": 2,
        "Employee": "Liam O'Brien",
        "Area": "Kitchen",
        "StartTime": "2024-03-22T11:00:00",
        "EndTime": "2024-03-22T22:00:00",
        "HoursScheduled": 11.0,
        "Status": "CONFIRMED",
    },
    {
        "Id": 103,
        "EmployeeId": 3,
        "Employee": "Maya Patel",
        "Area": "Bar",
        "StartTime": "2024-03-22T16:00:00",
        "EndTime": "2024-03-22T00:00:00",
        "HoursScheduled": 8.0,
        "Status": "CONFIRMED",
    },
    {
        "Id": 104,
        "EmployeeId": 4,
        "Employee": "Jake Williams",
        "Area": "FOH",
        "StartTime": "2024-03-22T17:00:00",
        "EndTime": "2024-03-22T23:00:00",
        "HoursScheduled": 6.0,
        "Status": "CONFIRMED",
    },
    {
        "Id": 105,
        "EmployeeId": 5,
        "Employee": "Amelia Torres",
        "Area": "Kitchen",
        "StartTime": "2024-03-22T11:00:00",
        "EndTime": "2024-03-22T21:00:00",
        "HoursScheduled": 10.0,
        "Status": "CONFIRMED",
    },
    {
        "Id": 106,
        "EmployeeId": 6,
        "Employee": "Connor Nguyen",
        "Area": "Bar",
        "StartTime": "2024-03-22T18:00:00",
        "EndTime": "2024-03-22T00:00:00",
        "HoursScheduled": 6.0,
        "Status": "OPEN",
    },
]

MOCK_TIMESHEETS = [
    {
        "Id": 201,
        "EmployeeId": 1,
        "Employee": "Sarah Chen",
        "Date": "2024-03-20",
        "StartTime": "10:02",
        "EndTime": "18:08",
        "HoursWorked": 8.1,
        "HourlyRate": 32.50,
        "TotalCost": 263.25,
        "Status": "APPROVED",
    },
    {
        "Id": 202,
        "EmployeeId": 2,
        "Employee": "Liam O'Brien",
        "Date": "2024-03-20",
        "StartTime": "11:05",
        "EndTime": "22:15",
        "HoursWorked": 11.17,
        "HourlyRate": 38.00,
        "TotalCost": 424.46,
        "Status": "APPROVED",
    },
    {
        "Id": 203,
        "EmployeeId": 3,
        "Employee": "Maya Patel",
        "Date": "2024-03-20",
        "StartTime": "15:58",
        "EndTime": "23:45",
        "HoursWorked": 7.78,
        "HourlyRate": 29.00,
        "TotalCost": 225.62,
        "Status": "PENDING",
    },
    {
        "Id": 204,
        "EmployeeId": 4,
        "Employee": "Jake Williams",
        "Date": "2024-03-20",
        "StartTime": "17:02",
        "EndTime": "22:58",
        "HoursWorked": 5.93,
        "HourlyRate": 24.50,
        "TotalCost": 145.29,
        "Status": "PENDING",
    },
]

MOCK_LEAVE = [
    {
        "Id": 301,
        "EmployeeId": 2,
        "Employee": "Liam O'Brien",
        "LeaveType": "Annual Leave",
        "DateFrom": "2024-04-01",
        "DateTo": "2024-04-05",
        "HoursRequested": 40.0,
        "Status": "PENDING",
        "Comment": "Easter break",
    },
    {
        "Id": 302,
        "EmployeeId": 4,
        "Employee": "Jake Williams",
        "LeaveType": "Sick Leave",
        "DateFrom": "2024-03-19",
        "DateTo": "2024-03-19",
        "HoursRequested": 8.0,
        "Status": "APPROVED",
    },
]

MOCK_LABOUR_COST = {
    "week": "2024-03-18 to 2024-03-24",
    "totalHours": 246.5,
    "totalCost": 7284.50,
    "labourCostPercentage": "26.4%",
    "totalRevenue": 27600.00,
    "byArea": {
        "Kitchen": {"hours": 98.0, "cost": 3234.00},
        "FOH": {"hours": 72.5, "cost": 1916.25},
        "Bar": {"hours": 56.0, "cost": 1568.00},
        "Management": {"hours": 20.0, "cost": 650.00},
    },
}


class DeputyClient(BaseClient):
    """Client for Deputy workforce management API."""

    def __init__(self, cfg: DeputyConfig, use_mock: bool = True):
        super().__init__(
            base_url=cfg.base_url,
            token=cfg.api_key,
            use_mock=use_mock or not cfg.configured,
        )

    async def _get_client(self):
        import httpx
        if self._client is None:
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
            if self.token:
                headers["Authorization"] = f"OAuth {self.token}"  # Deputy uses OAuth header
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=30.0,
            )
        return self._client

    async def get_employees(self, active_only: bool = True) -> dict:
        """Get all employees."""
        params = {"search[active]": "1"} if active_only else {}
        return await self.get("/resource/Employee", params)

    async def get_rosters(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        area: Optional[str] = None,
    ) -> dict:
        """Get roster/schedule."""
        params = {}
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
        return await self.get("/resource/Roster", params)

    async def get_timesheets(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        employee_id: Optional[int] = None,
        status: Optional[str] = None,
    ) -> dict:
        """Get timesheets."""
        params = {}
        if date_from:
            params["date_from"] = date_from
        if employee_id:
            params["employee_id"] = employee_id
        if status:
            params["status"] = status
        return await self.get("/resource/Timesheet", params)

    async def get_labour_cost(self, week_start: Optional[str] = None) -> dict:
        """Get labour cost summary for a week."""
        params = {"week_start": week_start} if week_start else {}
        return await self.get("/supervise/payroll", params)

    async def get_leave_requests(self, status: Optional[str] = None) -> dict:
        """Get leave requests."""
        params = {}
        if status:
            params["status"] = status
        return await self.get("/resource/Leave", params)

    async def approve_leave(self, leave_id: int) -> dict:
        """Approve a leave request."""
        return await self.post(f"/resource/Leave/{leave_id}/Approve", {})

    async def create_roster(self, roster_data: dict) -> dict:
        """Create a new roster entry."""
        return await self.post("/resource/Roster", roster_data)

    async def get_employee_by_id(self, employee_id: int) -> dict:
        """Get a specific employee."""
        return await self.get(f"/resource/Employee/{employee_id}", {})

    # ------------------------------------------------------------------
    # Mock overrides
    # ------------------------------------------------------------------

    async def _mock_get(self, path: str, params: dict) -> dict:
        if "/resource/Employee" in path and path.count("/") > 3:
            emp_id = int(path.split("/")[-1])
            emp = next((e for e in MOCK_EMPLOYEES if e["Id"] == emp_id), MOCK_EMPLOYEES[0])
            return {"Employee": emp, "mock": True}
        if "/resource/Employee" in path:
            emps = MOCK_EMPLOYEES
            if params.get("search[active]") == "1":
                emps = [e for e in emps if e["Active"]]
            return {"Employees": emps, "total": len(emps), "mock": True}
        if "/resource/Roster" in path:
            return {"Rosters": MOCK_ROSTERS, "total": len(MOCK_ROSTERS), "mock": True}
        if "/resource/Timesheet" in path:
            timesheets = MOCK_TIMESHEETS
            if params.get("employee_id"):
                timesheets = [t for t in timesheets if t["EmployeeId"] == params["employee_id"]]
            if params.get("status"):
                timesheets = [t for t in timesheets if t["Status"] == params["status"].upper()]
            return {"Timesheets": timesheets, "total": len(timesheets), "mock": True}
        if "/supervise/payroll" in path:
            return {**MOCK_LABOUR_COST, "mock": True}
        if "/resource/Leave" in path:
            leaves = MOCK_LEAVE
            if params.get("status"):
                leaves = [l for l in leaves if l["Status"] == params["status"].upper()]
            return {"Leave": leaves, "total": len(leaves), "mock": True}
        return {"mock": True, "path": path}

    async def _mock_post(self, path: str, data: dict) -> dict:
        if "Approve" in path:
            return {"mock": True, "approved": True, "message": "Leave request approved (mock)"}
        if "/resource/Roster" in path:
            return {"mock": True, "created": True, "Id": 999, "message": "Roster created (mock)"}
        return {"mock": True, "created": True}
