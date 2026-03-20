# hospo-mcp

**Model Context Protocol server for hospitality systems.**

Connect your AI agents and coding tools (Claude, Cursor, Copilot, GPT-4) directly to your hospitality tech stack — no custom integration code required.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/protocol-MCP-green.svg)](https://modelcontextprotocol.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## What It Does

`hospo-mcp` is a pre-built [Model Context Protocol](https://modelcontextprotocol.io) server that wraps the major hospitality business APIs into a single, AI-native interface:

| System | Integration | What You Can Do |
|--------|------------|-----------------|
| **Lightspeed O-Series** (Kounta) | ✅ | Orders, products, categories, sites, price updates |
| **Xero** | ✅ | P&L, invoices, cash flow, GST, supplier contacts |
| **Deputy** | ✅ | Roster, timesheets, labour cost, leave management |
| Lightspeed K-Series *(future adapter)* | 🔜 | Restaurant/K-Series API support |
| ResDiary *(coming soon)* | 🔜 | Bookings, covers, waitlist |
| SevenRooms *(coming soon)* | 🔜 | Reservations, guest profiles |
| MYOB *(coming soon)* | 🔜 | Payroll, BAS |

### Why MCP?

MCP lets AI tools talk directly to your business systems using a standard protocol. Instead of building custom integrations for every AI tool you use, you configure hospo-mcp once and any MCP-compatible client (Claude Desktop, Cursor, Continue, custom agents) gets instant access.

---

## Quick Start

### 1. Install

```bash
git clone https://github.com/HospitalityOwner-ai/hospo-mcp.git
cd hospo-mcp
pip install -e .
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env — or leave USE_MOCK_DATA=true to try it with realistic demo data
```

### 3. Run

```bash
hospo-mcp
```

The server starts in stdio mode (standard MCP transport), ready for any MCP client to connect.

---

## Connect to Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "hospo-mcp": {
      "command": "hospo-mcp",
      "env": {
        "USE_MOCK_DATA": "false",
        "LIGHTSPEED_ACCESS_TOKEN": "your_oauth_token",
        "LIGHTSPEED_SITE_ID": "your_site_id",
        "LIGHTSPEED_BASE_URL": "https://api.kounta.com/v1",
        "XERO_ACCESS_TOKEN": "your_token",
        "XERO_TENANT_ID": "your_tenant_id",
        "DEPUTY_API_KEY": "your_api_key",
        "DEPUTY_SUBDOMAIN": "myvenue"
      }
    }
  }
}
```

Or use mock data to test first:

```json
{
  "mcpServers": {
    "hospo-mcp": {
      "command": "hospo-mcp",
      "env": {
        "USE_MOCK_DATA": "true"
      }
    }
  }
}
```

## Connect to Cursor

In `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "hospo-mcp": {
      "command": "hospo-mcp",
      "env": {
        "USE_MOCK_DATA": "true"
      }
    }
  }
}
```

---

## Available Tools

### 🍺 Lightspeed O-Series (Kounta)

> **O-Series** (formerly Kounta, acquired by Lightspeed in 2019) is the dominant POS in
> Australian hospitality. The API lives at `api.kounta.com` and uses OAuth 2.0 Bearer tokens.
> Contact [developers@kounta.com](mailto:developers@kounta.com) for credentials.
> [API docs →](https://apidoc.kounta.com/)

| Tool | Description |
|------|-------------|
| `get_sales` | Orders for a date range (optionally scoped to a site) |
| `get_sales_summary` | Aggregated daily summary (revenue, transactions, hourly breakdown) |
| `get_menu_items` | Products with prices and categories |
| `get_sales_categories` | Revenue by category |
| `get_menu_item` | Single product by ID |
| `get_sites` | All sites/venues for the company |
| `update_item_price` | Update product price ⚠️ writes |

### 💰 Xero

| Tool | Description |
|------|-------------|
| `get_chart_of_accounts` | All accounts with balances |
| `get_invoices` | Invoices/bills with filters |
| `get_outstanding_invoices` | Unpaid invoices |
| `get_profit_and_loss` | P&L report for any date range |
| `get_cash_flow` | Cash flow summary |
| `get_suppliers` | Supplier contacts |
| `get_gst_summary` | GST/BAS position |
| `create_invoice` | Create invoice or bill ⚠️ writes |

### 👥 Deputy

| Tool | Description |
|------|-------------|
| `get_employees` | All staff with roles and rates |
| `get_roster` | Scheduled shifts by date range |
| `get_timesheets` | Actual hours worked with costs |
| `get_pending_timesheets` | Timesheets awaiting approval |
| `get_labour_cost` | Weekly labour cost vs revenue |
| `get_leave_requests` | Leave requests with status |
| `approve_leave_request` | Approve a leave request ⚠️ writes |
| `create_roster_shift` | Add a shift to the roster ⚠️ writes |
| `get_employee` | Single employee details |

---

## Resources (Live Data URIs)

Resources give MCP clients instant snapshots without calling tools:

| URI | Description |
|-----|-------------|
| `hospo://status` | Integration status (configured vs mock) |
| `hospo://sales/today` | Today's sales summary |
| `hospo://sales/categories` | Category revenue breakdown |
| `hospo://financials/pl` | Current month P&L |
| `hospo://financials/outstanding` | Outstanding invoices |
| `hospo://staff/roster` | Today's roster |
| `hospo://staff/labour-cost` | This week's labour costs |
| `hospo://staff/pending-approvals` | Timesheets + leave needing approval |

---

## Prompts (Guided Workflows)

Pre-built prompts for common hospo tasks:

| Prompt | Description |
|--------|-------------|
| `eod_report` | End-of-day business summary |
| `weekly_financial_review` | Weekly P&L, cash, labour, GST review |
| `roster_check` | Roster gap analysis and optimisation |
| `price_review` | Data-driven menu pricing analysis |
| `payroll_prep` | Payroll processing checklist |

---

## Example Conversations

Once connected, you can ask your AI:

```
"Give me today's trading summary"
→ Uses get_sales_summary + get_sales_categories

"Who's on shift tonight and what's the projected labour cost?"
→ Uses get_roster + get_labour_cost

"Any invoices I need to pay this week?"
→ Uses get_outstanding_invoices

"Run the weekly financial review"
→ Uses the weekly_financial_review prompt

"Prep me for payroll — what still needs approving?"
→ Uses get_pending_timesheets + get_leave_requests
```

---

## API Setup Guides

### Lightspeed O-Series (Kounta)
1. Contact [developers@kounta.com](mailto:developers@kounta.com) to get OAuth credentials
2. Complete the OAuth 2.0 flow to obtain an access token and refresh token
3. Find your Site ID in the O-Series back office (each venue has its own site ID)
4. Set `LIGHTSPEED_ACCESS_TOKEN`, `LIGHTSPEED_SITE_ID`, and `LIGHTSPEED_BASE_URL=https://api.kounta.com/v1` in your `.env`

> **K-Series users:** Lightspeed K-Series (Restaurant) uses a separate API at `api.lightspeedapp.com`.
> A K-Series adapter is planned for a future release.

### Xero
1. Create an app at [developer.xero.com](https://developer.xero.com/app/manage)
2. Complete OAuth 2.0 PKCE flow
3. Get your Tenant ID from the connections endpoint

### Deputy
1. Log in to your Deputy account
2. Go to Settings → API → Generate API Key
3. Your subdomain is the part before `.deputy.com` in your Deputy URL

---

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with debug logging
LOG_LEVEL=DEBUG hospo-mcp
```

### Project Structure

```
src/hospo_mcp/
├── server.py          # MCP server entry point
├── config.py          # Configuration management
├── clients/
│   ├── base.py        # Base HTTP client with mock support
│   ├── lightspeed.py  # Lightspeed POS client
│   ├── xero.py        # Xero accounting client
│   └── deputy.py      # Deputy workforce client
├── tools/
│   ├── lightspeed_tools.py
│   ├── xero_tools.py
│   └── deputy_tools.py
├── resources/
│   └── hospo_resources.py   # Live data URIs
└── prompts/
    └── hospo_prompts.py     # Guided workflow prompts
```

---

## Pricing

| Plan | Price | Venues | Support |
|------|-------|--------|---------|
| **Starter** | $49/mo | 1 venue | Email |
| **Growth** | $99/mo | Up to 3 venues | Priority |
| **Scale** | $149/mo | Unlimited | Dedicated |

[→ Get early access](https://hospitalityowner.ai/mcp)

---

## Roadmap

- [ ] ResDiary / SevenRooms bookings integration
- [ ] MYOB payroll integration  
- [ ] Tanda rostering support
- [ ] Token refresh handling (auto-refresh OAuth tokens)
- [ ] Webhook support (push events to MCP clients)
- [ ] Multi-venue routing (one server, multiple venues)
- [ ] Claude Desktop setup wizard

---

## Contributing

PRs welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

MIT — see [LICENSE](LICENSE).

---

Built by [HospitalityOwner.ai](https://hospitalityowner.ai) — AI tools for hospitality operators.
