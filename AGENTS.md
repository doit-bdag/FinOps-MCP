# FinOps MCP Server — Agent Instructions

This is a Model Context Protocol (MCP) server that provides FinOps Foundation
knowledge to AI coding agents. It exists so that code you write aligns with
FinOps best practices, FOCUS spec standards, and canonical terminology.

## When to Use This Server

Call this server's tools **before** writing any code that involves:

- Cloud cost data, billing schemas, or pricing models
- Cost allocation, chargeback, or showback logic
- Anomaly detection on cloud spend
- FOCUS-compliant data models or column definitions
- FinOps reporting, dashboards, or unit economics
- Commitment discounts (CUDs, Savings Plans, RIs)

## Dynamic Tool Loading (v0.3.0+)

This server uses **dynamic tool loading** to minimise context-window token
usage. Only 3 lightweight meta-tools are injected into your session at
startup (~800 tokens instead of ~12,000+).

### Workflow

```
1. list_finops_tools()            → discover tool names + 1-line descriptions
2. load_finops_tools([...])       → get full schemas for the tools you need
3. call_finops_tool(name, args)   → execute the selected tool
```

### Meta-Tools (always available)

| Tool                | Purpose                                                      |
| ------------------- | ------------------------------------------------------------ |
| `list_finops_tools` | List all available tools (optionally filter by category).    |
| `load_finops_tools` | Load full input schemas for selected tools.                  |
| `call_finops_tool`  | Execute any tool by name with arguments matching its schema. |

### Underlying Tools (accessed via `call_finops_tool`)

| Tool Name                | Category   | Description                                                                |
| ------------------------ | ---------- | -------------------------------------------------------------------------- |
| `search_finops_docs`     | search     | Semantic search over FinOps docs. First choice for cost/billing questions. |
| `get_finops_page`        | search     | Retrieve full text of a single FinOps document by URL.                     |
| `batch_get_finops_pages` | search     | Retrieve up to 20 documents in a single call.                              |
| `list_finops_sources`    | search     | List all indexed documentation pages.                                      |
| `trigger_finops_crawl`   | crawl      | Re-crawl and re-index a finops.org URL.                                    |
| `get_focus_column`       | compliance | Look up a FOCUS spec column definition (fuzzy matched).                    |
| `normalize_finops_term`  | compliance | Map informal language to canonical FinOps terminology.                     |
| `check_focus_compliance` | compliance | Validate a list of column names against the FOCUS spec.                    |
| `generate_ide_rules`     | generation | Generate a .cursorrules / AGENTS.md file for FinOps projects.              |

## Example Session

```
Agent: call list_finops_tools(category="compliance")
→ returns 3 compliance tools with 1-line descriptions

Agent: call load_finops_tools(["check_focus_compliance", "normalize_finops_term"])
→ returns full input schemas for those 2 tools

Agent: call call_finops_tool("check_focus_compliance", {"column_names": ["cost", "region"]})
→ returns compliance report with missing required columns
```

## Setup

If `search_finops_docs` returns no results, the index needs to be populated:

```bash
# From the repo root
uv run python scripts/ingest.py
```

## Terminology Guidance

When writing FinOps-related code, use canonical FinOps Foundation terminology:

| Say This             | Not This                                  |
| -------------------- | ----------------------------------------- |
| BilledCost           | bill amount, charge, raw cost             |
| EffectiveCost        | actual cost, real cost, net cost          |
| ListCost             | list price, on-demand price, retail price |
| CommitmentDiscountId | reservation ID, savings plan ID           |
| ChargeCategory       | cost type, charge type                    |
| ServiceName          | service, product                          |
