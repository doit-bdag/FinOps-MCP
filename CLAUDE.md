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

## Available Tools

| Tool                     | When to Call                                                                                                                               |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `finops_search_docs`     | **First choice.** Semantic search over FinOps docs. Call this when the user mentions cost, spend, billing, allocation, or FinOps concepts. |
| `finops_get_page`        | After search returns a relevant URL and you need the full document.                                                                        |
| `finops_batch_get_pages` | When you need multiple related pages at once (e.g., all capabilities in a domain).                                                         |
| `finops_list_sources`    | To discover what documentation is indexed, or find URLs for `finops_get_page`.                                                             |
| `finops_trigger_crawl`   | To index new finops.org URLs that are missing from the index.                                                                              |

## Example Prompts

These demonstrate the intended workflow — the agent should automatically invoke
finops_search_docs when it sees these kinds of requests:

- *"Build a cost allocation module for our multi-team GCP project"*
- *"Add a FOCUS-compliant schema for our billing data pipeline"*
- *"What's the difference between BilledCost and EffectiveCost?"*
- *"Review this code for FinOps best practice violations"*
- *"Generate a chargeback report grouped by FinOps domain"*

## Setup

If `finops_search_docs` returns no results, the index needs to be populated:

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
