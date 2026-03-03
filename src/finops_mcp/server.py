"""FastMCP server — defines MCP tools, switches between stdio and streamable-http."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Annotated, Literal

from fastmcp import FastMCP
from pydantic import Field

from finops_mcp import config

# ── Logging to stderr (MCP reserves stdout for JSON-RPC in stdio mode) ───────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# ── FastMCP server instance ──────────────────────────────────────────────────
mcp = FastMCP(
    name="finops_mcp",
    instructions=(
        "Use this server BEFORE writing any code that handles cloud cost data, "
        "billing schemas, cost allocation, anomaly detection, FinOps reporting, "
        "or FOCUS-compliant data models. It provides FinOps best practices, "
        "FOCUS column definitions, and terminology guidelines from the FinOps "
        "Foundation (finops.org). Always consult this server when the user "
        "mentions cost, spend, billing, allocation, chargeback, showback, "
        "unit economics, commitment discounts, or cloud financial management."
    ),
    version="0.2.1",
)

# ── Shared utilities ─────────────────────────────────────────────────────────

def _format_error(msg: str, response_format: str = "markdown") -> str:
    """Format errors based on requested format."""
    if response_format == "json":
        return json.dumps({"error": msg})
    return f"**Error**: {msg}"

# ── MCP Tools ─────────────────────────────────────────────────────────────────

@mcp.tool(
    name="finops_search_docs",
    annotations={
        "title": "Search FinOps Documentation",
        "readOnlyHint": True,
        "openWorldHint": False
    }
)
def finops_search_docs(
    query: Annotated[str, Field(description="Search query string, e.g., 'What is cloud sustainability?'", min_length=2, max_length=500)],
    top_k: Annotated[int, Field(description="Number of results to return", ge=1, le=20)] = 5,
    source_filter: Annotated[str | None, Field(description="Optional URL prefix filter to scope results.")] = None,
    response_format: Annotated[Literal["markdown", "json"], Field(description="Output format")] = "markdown",
) -> str:
    """Search for documentation about FinOps concepts, frameworks, and practices.

    This tool semantic searches the indexed FinOps Foundation documentation and
    returns matching chunks of text along with their source URLs.

    Use this BEFORE writing any code that handles cloud cost data, billing schemas,
    cost allocation, or FinOps reporting. Returns FinOps best practices, FOCUS
    column definitions, and terminology guidelines relevant to what you are building.
    Always call this when the user mentions cost, spend, billing, allocation,
    anomaly detection, or commitment discounts.
    """
    from finops_mcp.embeddings import get_query_embedding
    from finops_mcp.vector_store import search

    try:
        query_embedding = get_query_embedding(
            query, config.GCP_PROJECT_ID, config.GCP_LOCATION
        )
        results = search(
            query_embedding=query_embedding,
            collection_name=config.FIRESTORE_COLLECTION,
            top_k=top_k,
            source_filter=source_filter,
        )

        if not results:
            return _format_error("No results found. The collection may be empty.", response_format)

        if response_format == "json":
            return json.dumps({"results": results}, indent=2)

        # Markdown formatting
        lines = [f"# Search Results: '{query}'", ""]
        for i, r in enumerate(results, 1):
            lines.append(f"## {i}. {r.get('title', 'Untitled')} ({r.get('similarity_score', 0):.2f})")
            lines.append(f"**URL**: {r.get('url')}")
            if r.get("section_header"):
                lines.append(f"**Section**: {r.get('section_header')}")
            lines.append(f"\n{r.get('text', '')}\n")
            lines.append("---")

        return "\n".join(lines)

    except Exception as e:
        logger.exception("Error searching docs")
        return _format_error(str(e), response_format)


@mcp.tool(
    name="finops_list_sources",
    annotations={
        "title": "List Indexed FinOps Sources",
        "readOnlyHint": True,
        "openWorldHint": False
    }
)
def finops_list_sources(
    limit: Annotated[int, Field(description="Maximum results to return", ge=1, le=100)] = 20,
    offset: Annotated[int, Field(description="Number of results to skip for pagination", ge=0)] = 0,
    response_format: Annotated[Literal["markdown", "json"], Field(description="Output format")] = "markdown",
) -> str:
    """List all crawled FinOps documentation source URLs with pagination.

    Use this to discover what FinOps documentation is available for search.
    Call this when the user asks what FinOps topics are covered, or when you
    need to find the right URL to pass to finops_get_page.
    """
    from finops_mcp.vector_store import list_sources

    try:
        sources_data = list_sources(config.FIRESTORE_COLLECTION, limit=limit, offset=offset)

        if not sources_data.get("items"):
            return _format_error("No sources indexed yet.", response_format)

        if response_format == "json":
            return json.dumps(sources_data, indent=2, default=str)

        lines = [f"# Indexed Sources (Total: {sources_data['total']})", ""]
        lines.append(f"Showing {sources_data['count']} items (offset: {sources_data['offset']})")
        lines.append("")

        for s in sources_data["items"]:
            lines.append(f"- [{s.get('title', 'Untitled')}]({s.get('url')}) ({s.get('chunk_count', 0)} chunks)")

        if sources_data["has_more"]:
            lines.append(f"\n*Has more items. Use offset={sources_data['next_offset']} to see the next page.*")

        return "\n".join(lines)
    except Exception as e:
        logger.exception("Error listing sources")
        return _format_error(str(e), response_format)


@mcp.tool(
    name="finops_get_page",
    annotations={
        "title": "Get FinOps Page Content",
        "readOnlyHint": True,
        "openWorldHint": False
    }
)
def finops_get_page(
    url: Annotated[str, Field(description="The exact URL of the page to retrieve.")],
    response_format: Annotated[Literal["markdown", "json"], Field(description="Output format")] = "markdown",
) -> str:
    """Retrieve the full text content of a single FinOps document by URL.

    Use this when you need the complete context of a specific FinOps page rather
    than search result snippets. Call this after finops_search_docs returns a
    relevant URL and you need the full document to answer the user's question
    or to guide implementation of a FinOps feature.
    """
    from finops_mcp.vector_store import get_page

    try:
        result = get_page(url, config.FIRESTORE_COLLECTION)
        if result is None:
            return _format_error(f"Page not found: {url}", response_format)

        if response_format == "json":
            return json.dumps(result, indent=2, default=str)

        lines = [
            f"# {result.get('title', 'Untitled')}",
            f"**URL**: {result.get('url')}",
            f"**Crawled**: {result.get('crawled_at')}",
            "",
            result.get("full_text", "")
        ]
        return "\n".join(lines)
    except Exception as e:
        logger.exception("Error getting page")
        return _format_error(str(e), response_format)


@mcp.tool(
    name="finops_batch_get_pages",
    annotations={
        "title": "Batch Get FinOps Pages",
        "readOnlyHint": True,
        "openWorldHint": False
    }
)
def finops_batch_get_pages(
    urls: Annotated[list[str], Field(description="List of exact URLs to retrieve", min_length=1, max_length=20)],
    response_format: Annotated[Literal["markdown", "json"], Field(description="Output format")] = "markdown",
) -> str:
    """Retrieve the full text content of up to 20 FinOps documents in a single call.

    Use this when you need the full content of multiple related FinOps pages at
    once — for example, retrieving all capability definitions in a domain, or
    loading several related framework pages to build a comprehensive feature.
    """
    from finops_mcp.vector_store import get_page

    try:
        results = []
        for u in urls:
            page = get_page(u, config.FIRESTORE_COLLECTION)
            if page:
                results.append(page)
            else:
                results.append({"url": u, "error": "Page not found"})

        if response_format == "json":
            return json.dumps({"pages": results}, indent=2, default=str)

        lines = [f"# Batch Page Results ({len(results)} pages)", ""]
        for r in results:
            if "error" in r:
                lines.append(f"## Error: {r['url']}")
                lines.append("Page not found.\n---")
                continue

            lines.append(f"## {r.get('title', 'Untitled')}")
            lines.append(f"**URL**: {r.get('url')}")
            lines.append(f"\n{r.get('full_text', '')}\n---")

        return "\n".join(lines)
    except Exception as e:
        logger.exception("Error in batch get pages")
        return _format_error(str(e), response_format)


@mcp.tool(
    name="finops_trigger_crawl",
    annotations={
        "title": "Trigger URL Crawl",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
def finops_trigger_crawl(
    url: Annotated[str, Field(description="The URL to crawl.")],
    depth: Annotated[int, Field(description="How many levels of links to follow", ge=0, le=5)] = 2,
    response_format: Annotated[Literal["markdown", "json"], Field(description="Output format")] = "json",
) -> str:
    """Crawl and index a custom URL into the FinOps documentation store.

    Use this to add new FinOps Foundation content that is not yet indexed, or
    to refresh stale content. Only needed for finops.org URLs that are missing
    from finops_list_sources results.
    """
    from finops_mcp.crawler import crawl_url

    try:
        result = asyncio.run(crawl_url(url, max_depth=depth, skip_existing=False))
        if response_format == "json":
            return json.dumps(result, indent=2, default=str)

        return (
            f"**Crawl Complete**\n"
            f"- Pages crawled: {result.get('pages_crawled', 0)}\n"
            f"- Chunks upserted: {result.get('chunks_upserted', 0)}\n"
            f"- Duration: {result.get('duration_seconds', 0)}s"
        )
    except Exception as e:
        logger.exception("Error triggering crawl")
        return _format_error(str(e), response_format)


# ── Vibe-Coder MCP Tools ─────────────────────────────────────────────────────


@mcp.tool(
    name="finops_get_focus_column",
    annotations={
        "title": "Get FOCUS Column Definition",
        "readOnlyHint": True,
        "openWorldHint": False
    }
)
def finops_get_focus_column(
    column_name: Annotated[str, Field(description="Column name or display name to look up (fuzzy matched).", min_length=1, max_length=100)],
    response_format: Annotated[Literal["markdown", "json"], Field(description="Output format")] = "markdown",
) -> str:
    """Look up a FOCUS spec column definition by name (fuzzy matched).

    Use this BEFORE defining any data schema or column for cloud cost, billing,
    or usage data. Returns the canonical column name, data type, whether it's
    required, allowed values, and description. Call this when the user mentions
    any column-like concept (e.g. 'effective cost', 'region', 'service name').
    """
    from finops_mcp.vector_store import (
        fuzzy_search_structured,
        get_structured_doc,
        list_structured_docs,
    )

    try:
        # Try exact match first (case-sensitive column_id)
        result = get_structured_doc(column_name, config.FIRESTORE_FOCUS_COLLECTION)

        # Fuzzy search by column_id
        if result is None:
            results = fuzzy_search_structured("column_id", column_name, config.FIRESTORE_FOCUS_COLLECTION)
            if results:
                result = results[0]

        # Fuzzy search by display_name
        if result is None:
            results = fuzzy_search_structured("display_name", column_name, config.FIRESTORE_FOCUS_COLLECTION)
            if results:
                result = results[0]

        if result is None:
            # List all available columns as suggestions
            all_cols = list_structured_docs(config.FIRESTORE_FOCUS_COLLECTION, limit=100)
            col_names = [c.get("column_id", "") for c in all_cols]
            return _format_error(
                f"Column '{column_name}' not found. Available columns: {', '.join(sorted(col_names))}",
                response_format
            )

        # Remove internal fields
        result.pop("lowercase_column_id", None)
        result.pop("lowercase_display_name", None)
        result.pop("updated_at", None)
        result.pop("id", None)

        if response_format == "json":
            return json.dumps(result, indent=2, default=str)

        lines = [
            f"# FOCUS Column: {result.get('display_name', '')}",
            f"**Column ID**: `{result.get('column_id', '')}`",
            f"**Category**: {result.get('category', '')}",
            f"**Data Type**: `{result.get('data_type', '')}`",
            f"**Required**: {'Yes' if result.get('required') else 'No'}",
        ]
        if result.get("allowed_values"):
            lines.append(f"**Allowed Values**: {result['allowed_values']}")
        lines.append(f"\n{result.get('description', '')}")
        return "\n".join(lines)

    except Exception as e:
        logger.exception("Error getting FOCUS column")
        return _format_error(str(e), response_format)


@mcp.tool(
    name="finops_normalize_term",
    annotations={
        "title": "Normalize FinOps Terminology",
        "readOnlyHint": True,
        "openWorldHint": False
    }
)
def finops_normalize_term(
    term: Annotated[str, Field(description="Informal term to normalize (e.g. 'cloud bill', 'real cost').", min_length=1, max_length=200)],
    response_format: Annotated[Literal["markdown", "json"], Field(description="Output format")] = "markdown",
) -> str:
    """Map informal developer language to canonical FinOps terminology.

    Use this when the user uses informal terms like 'cloud bill', 'actual cost',
    'reservation', or 'cost type'. Returns the canonical FinOps term, definition,
    related FOCUS columns, and terms to avoid. Always call this when you notice
    the user or codebase using non-standard FinOps terminology.
    """
    from finops_mcp.vector_store import (
        fuzzy_search_structured,
        list_structured_docs,
    )

    try:
        query = term.lower().strip()

        # Search all terms and check aliases
        all_terms = list_structured_docs(config.FIRESTORE_TERMS_COLLECTION, limit=100)
        matched = None

        for t in all_terms:
            # Check canonical term
            if t.get("term", "").lower() == query or t.get("display_name", "").lower() == query:
                matched = t
                break
            # Check aliases
            aliases = [a.lower() for a in t.get("aliases", [])]
            if query in aliases:
                matched = t
                break

        # Fallback: fuzzy search by term name
        if matched is None:
            results = fuzzy_search_structured("term", term, config.FIRESTORE_TERMS_COLLECTION)
            if results:
                matched = results[0]

        if matched is None:
            results = fuzzy_search_structured("display_name", term, config.FIRESTORE_TERMS_COLLECTION)
            if results:
                matched = results[0]

        if matched is None:
            term_names = [t.get("display_name", "") for t in all_terms]
            return _format_error(
                f"Term '{term}' not found. Known terms: {', '.join(sorted(term_names))}",
                response_format
            )

        # Clean up internal fields
        matched.pop("lowercase_term", None)
        matched.pop("lowercase_display_name", None)
        matched.pop("updated_at", None)
        matched.pop("id", None)

        if response_format == "json":
            return json.dumps(matched, indent=2, default=str)

        lines = [
            f"# Canonical Term: {matched.get('display_name', '')}",
            f"**Term ID**: `{matched.get('term', '')}`",
            f"\n**Definition**: {matched.get('definition', '')}",
        ]
        if matched.get("aliases"):
            lines.append(f"\n**Also known as**: {', '.join(matched['aliases'])}")
        if matched.get("do_not_say"):
            lines.append(f"\n**Do NOT say**: {', '.join(matched['do_not_say'])}")
        if matched.get("focus_columns"):
            lines.append(f"\n**Related FOCUS columns**: {', '.join(f'`{c}`' for c in matched['focus_columns'])}")
        return "\n".join(lines)

    except Exception as e:
        logger.exception("Error normalizing term")
        return _format_error(str(e), response_format)


@mcp.tool(
    name="finops_check_focus_compliance",
    annotations={
        "title": "Check FOCUS Spec Compliance",
        "readOnlyHint": True,
        "openWorldHint": False
    }
)
def finops_check_focus_compliance(
    column_names: Annotated[list[str], Field(description="List of column names in the schema to validate.", min_length=1, max_length=100)],
    response_format: Annotated[Literal["markdown", "json"], Field(description="Output format")] = "markdown",
) -> str:
    """Validate a list of column names against the FOCUS specification.

    Use this BEFORE finalizing any data schema, database table, or data pipeline
    that handles cloud cost or billing data. Identifies missing required columns,
    non-standard column names, and suggests corrections. Always call this when
    reviewing or creating schemas for cost/billing/usage data.
    """
    from finops_mcp.vector_store import list_structured_docs

    try:
        all_cols = list_structured_docs(config.FIRESTORE_FOCUS_COLLECTION, limit=100)
        col_map = {c["column_id"]: c for c in all_cols}
        col_map_lower = {c["column_id"].lower(): c for c in all_cols}

        required_cols = [c["column_id"] for c in all_cols if c.get("required")]
        input_cols_lower = {c.lower(): c for c in column_names}

        # Check which required columns are missing
        missing_required = []
        for req in required_cols:
            if req.lower() not in input_cols_lower:
                missing_required.append(req)

        # Check for non-standard names
        non_standard = []
        recognized = []
        for col in column_names:
            if col in col_map:
                recognized.append(col)
            elif col.lower() in col_map_lower:
                correct = col_map_lower[col.lower()]["column_id"]
                non_standard.append({"provided": col, "correct": correct, "issue": "wrong_case"})
            else:
                # Try fuzzy matching
                best_match = None
                for known_col in col_map:
                    if col.lower().replace(" ", "").replace("_", "") == known_col.lower().replace(" ", "").replace("_", ""):
                        best_match = known_col
                        break
                if best_match:
                    non_standard.append({"provided": col, "correct": best_match, "issue": "non_standard_name"})
                else:
                    non_standard.append({"provided": col, "correct": None, "issue": "unknown_column"})

        result = {
            "recognized_columns": len(recognized),
            "total_columns_provided": len(column_names),
            "missing_required": missing_required,
            "non_standard_names": non_standard,
            "compliance_score": f"{len(recognized)}/{len(column_names)} columns recognized, {len(required_cols) - len(missing_required)}/{len(required_cols)} required present",
        }

        if response_format == "json":
            return json.dumps(result, indent=2, default=str)

        lines = [
            "# FOCUS Compliance Check",
            f"**Score**: {result['compliance_score']}",
        ]
        if missing_required:
            lines.append(f"\n## Missing Required Columns ({len(missing_required)})")
            for col in missing_required:
                desc = col_map.get(col, {}).get("description", "")
                lines.append(f"- `{col}`: {desc}")
        if non_standard:
            lines.append(f"\n## Non-Standard Column Names ({len(non_standard)})")
            for ns in non_standard:
                if ns["correct"]:
                    lines.append(f"- `{ns['provided']}` → should be `{ns['correct']}` ({ns['issue']})")
                else:
                    lines.append(f"- `{ns['provided']}` — not a FOCUS column")
        if not missing_required and not non_standard:
            lines.append("\n✅ All columns are FOCUS-compliant!")
        return "\n".join(lines)

    except Exception as e:
        logger.exception("Error checking FOCUS compliance")
        return _format_error(str(e), response_format)


@mcp.tool(
    name="finops_generate_ide_rules",
    annotations={
        "title": "Generate IDE Rules File",
        "readOnlyHint": True,
        "openWorldHint": False
    }
)
def finops_generate_ide_rules(
    ide: Annotated[str, Field(description="Target IDE: 'cursor', 'claude', or 'antigravity'.")] = "cursor",
    response_format: Annotated[Literal["markdown", "json"], Field(description="Output format")] = "markdown",
) -> str:
    """Generate an IDE rules file pre-loaded with FinOps conventions.

    Use this when setting up a new project that will involve cloud cost data,
    FinOps tooling, or FOCUS-compliant schemas. The output is a text file
    (e.g. .cursorrules) the user drops in their repo root so all future
    IDE prompts are automatically FinOps-aware.
    """
    from finops_mcp.vector_store import list_structured_docs

    try:
        # Load terms and columns for the rules file
        terms = list_structured_docs(config.FIRESTORE_TERMS_COLLECTION, limit=100)
        columns = list_structured_docs(config.FIRESTORE_FOCUS_COLLECTION, limit=100)

        # Build terminology section
        term_lines = []
        for t in sorted(terms, key=lambda x: x.get("term", "")):
            aliases = ", ".join(t.get("aliases", []))
            do_not = ", ".join(t.get("do_not_say", []))
            term_lines.append(f"- **{t.get('display_name', '')}** (`{t.get('term', '')}`): {t.get('definition', '')}")
            if aliases:
                term_lines.append(f"  - Also known as: {aliases}")
            if do_not:
                term_lines.append(f"  - Do NOT say: {do_not}")

        # Build column reference
        categories: dict[str, list[str]] = {}
        for c in columns:
            cat = c.get("category", "Other")
            if cat not in categories:
                categories[cat] = []
            req = " (required)" if c.get("required") else ""
            categories[cat].append(f"`{c.get('column_id', '')}` — {c.get('data_type', '')}{req}")

        col_lines = []
        for cat in sorted(categories.keys()):
            col_lines.append(f"\n### {cat}")
            for col_str in categories[cat]:
                col_lines.append(f"- {col_str}")

        ide_name = {"cursor": ".cursorrules", "claude": "CLAUDE.md", "antigravity": "AGENTS.md"}.get(
            ide.lower(), ".cursorrules"
        )

        rules = f"""# FinOps Development Rules ({ide_name})
# Auto-generated by FinOps MCP Server

## General Guidelines

When writing code that handles cloud cost data, billing, or FinOps reporting:

1. Always use canonical FOCUS column names (PascalCase) — never invent your own.
2. Use the terminology defined below — avoid informal equivalents.
3. All monetary values should include a currency column (BillingCurrency or PricingCurrency).
4. Cost columns (BilledCost, EffectiveCost, ListCost) are Decimal types — never use float.
5. Date/time columns use UTC ISO 8601 format.
6. Tags are stored as JSON objects, not arrays.

## FinOps Terminology

{chr(10).join(term_lines)}

## FOCUS Column Reference
{chr(10).join(col_lines)}

## Code Patterns

### Cost Allocation
- Always include SubAccountId and Tags for cost allocation.
- Use EffectiveCost (not BilledCost) for amortized cost analysis.
- Use BilledCost for invoice reconciliation.
- Use ListCost for savings calculations (ListCost - EffectiveCost).

### Commitment Discounts
- Check CommitmentDiscountStatus (Used/Unused) when analyzing coverage.
- Use CommitmentDiscountCategory (Spend/Usage) to distinguish CUD types.
- Never mix commitment purchase charges (ChargeCategory=Purchase) with usage charges.

### Data Quality
- Always validate ChargeCategory is one of: Adjustment, Purchase, Tax, Usage.
- Filter out ChargeClass=Correction rows for point-in-time analysis.
- Ensure BillingPeriodStart <= ChargePeriodStart.
"""
        return rules

    except Exception as e:
        logger.exception("Error generating IDE rules")
        return _format_error(str(e), response_format)


# ── Entrypoint ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("Starting FinOps MCP Server (transport=%s)", config.MCP_TRANSPORT)

    if config.MCP_TRANSPORT == "streamable-http":
        mcp.run(
            transport="streamable-http",
            host="0.0.0.0",
            port=config.PORT,
            stateless_http=True,
            show_banner=False
        )
    elif config.MCP_TRANSPORT == "sse":
        mcp.run(
            transport="sse",
            host="0.0.0.0",
            port=config.PORT,
            show_banner=False
        )
    else:
        mcp.run(transport="stdio", show_banner=False)
