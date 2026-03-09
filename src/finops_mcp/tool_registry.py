"""Tool registry for dynamic tool loading.

Maps tool names to metadata (category, descriptions, input schemas) and
handler callables.  The handlers are plain functions defined in server.py —
they are NOT decorated with @mcp.tool() so their schemas do not inflate the
context window on session start.
"""

from __future__ import annotations

from typing import Any, Callable

# Lazy import: handlers are bound at first access via _ensure_handlers().
_handlers_bound = False


def _ensure_handlers() -> None:
    """Bind handler references on first use (avoids circular imports)."""
    global _handlers_bound
    if _handlers_bound:
        return

    from finops_mcp import server as srv

    TOOL_REGISTRY["search_finops_docs"]["handler"] = srv.finops_search_docs
    TOOL_REGISTRY["list_finops_sources"]["handler"] = srv.finops_list_sources
    TOOL_REGISTRY["get_finops_page"]["handler"] = srv.finops_get_page
    TOOL_REGISTRY["batch_get_finops_pages"]["handler"] = srv.finops_batch_get_pages
    TOOL_REGISTRY["trigger_finops_crawl"]["handler"] = srv.finops_trigger_crawl
    TOOL_REGISTRY["get_focus_column"]["handler"] = srv.finops_get_focus_column
    TOOL_REGISTRY["normalize_finops_term"]["handler"] = srv.finops_normalize_term
    TOOL_REGISTRY["check_focus_compliance"]["handler"] = srv.finops_check_focus_compliance
    TOOL_REGISTRY["generate_ide_rules"]["handler"] = srv.finops_generate_ide_rules

    _handlers_bound = True


# ── Registry ──────────────────────────────────────────────────────────────────

TOOL_REGISTRY: dict[str, dict[str, Any]] = {
    # ── Search / retrieval ────────────────────────────────────────────────
    "search_finops_docs": {
        "name": "search_finops_docs",
        "category": "search",
        "short_description": "Semantic search over indexed FinOps Foundation docs.",
        "full_description": (
            "Semantic search over FinOps Foundation documentation. Use BEFORE writing "
            "any code that handles cloud cost data, billing schemas, cost allocation, "
            "or FinOps reporting. Always call when the user mentions cost, spend, "
            "billing, allocation, anomaly detection, or FinOps capabilities."
        ),
        "input_schema": {
            "query": {
                "type": "string",
                "required": True,
                "description": "Search query string, e.g., 'What is cloud sustainability?'",
            },
            "top_k": {
                "type": "integer",
                "default": 5,
                "min": 1,
                "max": 20,
                "description": "Number of results to return",
            },
            "source_filter": {
                "type": "string",
                "required": False,
                "description": "Optional URL prefix filter to scope results.",
            },
            "response_format": {
                "type": "string",
                "enum": ["markdown", "json"],
                "default": "markdown",
                "description": "Output format",
            },
        },
        "returns": "Formatted search results with text, url, title, section_header, similarity_score",
        "example": {"query": "FinOps crawl phase capabilities", "top_k": 5},
        "handler": None,  # bound lazily
    },
    "list_finops_sources": {
        "name": "list_finops_sources",
        "category": "search",
        "short_description": "List all indexed FinOps Foundation documentation pages.",
        "full_description": (
            "Returns all URLs and page titles that have been crawled and indexed. "
            "Use to discover what documentation is available for search, or to find "
            "the exact URL for get_finops_page."
        ),
        "input_schema": {
            "limit": {
                "type": "integer",
                "default": 20,
                "min": 1,
                "max": 100,
                "description": "Maximum results to return",
            },
            "offset": {
                "type": "integer",
                "default": 0,
                "min": 0,
                "description": "Number of results to skip for pagination",
            },
            "response_format": {
                "type": "string",
                "enum": ["markdown", "json"],
                "default": "markdown",
                "description": "Output format",
            },
        },
        "returns": "Paginated list of indexed source URLs with titles and chunk counts",
        "example": {"limit": 20, "offset": 0},
        "handler": None,
    },
    "get_finops_page": {
        "name": "get_finops_page",
        "category": "search",
        "short_description": "Retrieve the full text of a single FinOps document by URL.",
        "full_description": (
            "Retrieve the full text content of a single FinOps document by URL. "
            "Use when you need the complete context of a specific FinOps page rather "
            "than search result snippets. Call after search_finops_docs returns a "
            "relevant URL and you need the full document."
        ),
        "input_schema": {
            "url": {
                "type": "string",
                "required": True,
                "description": "The exact URL of the page to retrieve.",
            },
            "response_format": {
                "type": "string",
                "enum": ["markdown", "json"],
                "default": "markdown",
                "description": "Output format",
            },
        },
        "returns": "Full page content with title, URL, and crawled timestamp",
        "example": {"url": "https://www.finops.org/framework/"},
        "handler": None,
    },
    "batch_get_finops_pages": {
        "name": "batch_get_finops_pages",
        "category": "search",
        "short_description": "Retrieve full text of up to 20 FinOps documents in one call.",
        "full_description": (
            "Retrieve the full text content of up to 20 FinOps documents in a single "
            "call. Use when you need multiple related pages at once — for example, "
            "retrieving all capability definitions in a domain, or loading several "
            "related framework pages to build a comprehensive feature."
        ),
        "input_schema": {
            "urls": {
                "type": "array",
                "items": {"type": "string"},
                "required": True,
                "min_items": 1,
                "max_items": 20,
                "description": "List of exact URLs to retrieve",
            },
            "response_format": {
                "type": "string",
                "enum": ["markdown", "json"],
                "default": "markdown",
                "description": "Output format",
            },
        },
        "returns": "Batch of full page contents with titles and URLs",
        "example": {"urls": ["https://www.finops.org/framework/", "https://www.finops.org/focus/"]},
        "handler": None,
    },

    # ── Crawl ─────────────────────────────────────────────────────────────
    "trigger_finops_crawl": {
        "name": "trigger_finops_crawl",
        "category": "crawl",
        "short_description": "Re-crawl and re-index a FinOps Foundation URL.",
        "full_description": (
            "Crawl and index a custom URL into the FinOps documentation store. "
            "Use to add new FinOps Foundation content that is not yet indexed, or "
            "to refresh stale content. Only needed for finops.org URLs that are "
            "missing from list_finops_sources results."
        ),
        "input_schema": {
            "url": {
                "type": "string",
                "required": True,
                "description": "The URL to crawl.",
            },
            "depth": {
                "type": "integer",
                "default": 2,
                "min": 0,
                "max": 5,
                "description": "How many levels of links to follow",
            },
            "response_format": {
                "type": "string",
                "enum": ["markdown", "json"],
                "default": "json",
                "description": "Output format",
            },
        },
        "returns": "Crawl summary with pages_crawled, chunks_upserted, and duration_seconds",
        "example": {"url": "https://www.finops.org/focus/", "depth": 2},
        "handler": None,
    },

    # ── Compliance / terminology ──────────────────────────────────────────
    "get_focus_column": {
        "name": "get_focus_column",
        "category": "compliance",
        "short_description": "Return FOCUS spec definition for a column by name (fuzzy matched).",
        "full_description": (
            "Look up a FOCUS spec column definition by name (fuzzy matched). "
            "Use BEFORE defining any data schema or column for cloud cost, billing, "
            "or usage data. Returns the canonical column name, data type, whether it's "
            "required, allowed values, and description. Call when the user mentions "
            "any column-like concept (e.g. 'effective cost', 'region', 'service name')."
        ),
        "input_schema": {
            "column_name": {
                "type": "string",
                "required": True,
                "description": "Column name or display name to look up (fuzzy matched).",
            },
            "response_format": {
                "type": "string",
                "enum": ["markdown", "json"],
                "default": "markdown",
                "description": "Output format",
            },
        },
        "returns": "Column definition with column_id, data_type, required, allowed_values, description",
        "example": {"column_name": "EffectiveCost"},
        "handler": None,
    },
    "normalize_finops_term": {
        "name": "normalize_finops_term",
        "category": "compliance",
        "short_description": "Map informal developer language to canonical FinOps terminology.",
        "full_description": (
            "Map informal developer language to canonical FinOps terminology. "
            "Use when the user uses informal terms like 'cloud bill', 'actual cost', "
            "'reservation', or 'cost type'. Returns the canonical FinOps term, "
            "definition, related FOCUS columns, and terms to avoid. Always call "
            "when you notice non-standard FinOps terminology."
        ),
        "input_schema": {
            "term": {
                "type": "string",
                "required": True,
                "description": "Informal term to normalize (e.g. 'cloud bill', 'real cost').",
            },
            "response_format": {
                "type": "string",
                "enum": ["markdown", "json"],
                "default": "markdown",
                "description": "Output format",
            },
        },
        "returns": "Canonical term with definition, aliases, do_not_say list, and related FOCUS columns",
        "example": {"term": "actual cost"},
        "handler": None,
    },
    "check_focus_compliance": {
        "name": "check_focus_compliance",
        "category": "compliance",
        "short_description": "Validate column names against the FOCUS specification.",
        "full_description": (
            "Validate a list of column names against the FOCUS specification. "
            "Use BEFORE finalizing any data schema, database table, or data pipeline "
            "that handles cloud cost or billing data. Identifies missing required "
            "columns, non-standard column names, and suggests corrections. Always "
            "call when reviewing or creating schemas for cost/billing/usage data."
        ),
        "input_schema": {
            "column_names": {
                "type": "array",
                "items": {"type": "string"},
                "required": True,
                "min_items": 1,
                "max_items": 100,
                "description": "List of column names in the schema to validate.",
            },
            "response_format": {
                "type": "string",
                "enum": ["markdown", "json"],
                "default": "markdown",
                "description": "Output format",
            },
        },
        "returns": "Compliance report with recognized_columns, missing_required, non_standard_names, and score",
        "example": {"column_names": ["BilledCost", "RegionName", "ServiceName"]},
        "handler": None,
    },

    # ── Generation ────────────────────────────────────────────────────────
    "generate_ide_rules": {
        "name": "generate_ide_rules",
        "category": "generation",
        "short_description": "Generate a .cursorrules / AGENTS.md file for FinOps projects.",
        "full_description": (
            "Generate an IDE rules file pre-loaded with FinOps conventions. "
            "Use when setting up a new project that will involve cloud cost data, "
            "FinOps tooling, or FOCUS-compliant schemas. The output is a text file "
            "(e.g. .cursorrules) the user drops in their repo root so all future "
            "IDE prompts are automatically FinOps-aware."
        ),
        "input_schema": {
            "ide": {
                "type": "string",
                "default": "cursor",
                "enum": ["cursor", "claude", "antigravity"],
                "description": "Target IDE: 'cursor', 'claude', or 'antigravity'.",
            },
            "response_format": {
                "type": "string",
                "enum": ["markdown", "json"],
                "default": "markdown",
                "description": "Output format",
            },
        },
        "returns": "String containing the IDE rules file content to write",
        "example": {"ide": "cursor"},
        "handler": None,
    },
}


def get_tool_handler(tool_name: str) -> Callable[..., str] | None:
    """Return the callable handler for a tool, or None if not found."""
    _ensure_handlers()
    entry = TOOL_REGISTRY.get(tool_name)
    if entry is None:
        return None
    return entry["handler"]
