"""FastMCP server — defines MCP tools, switches between stdio and streamable-http."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from enum import Enum

from fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field, field_validator

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
        "A server that provides semantic search and retrieval over "
        "FinOps Foundation documentation (finops.org)."
    ),
    version="0.1.0",
)

# ── Enums & Pydantic Models ──────────────────────────────────────────────────

class ResponseFormat(str, Enum):
    """Output format for tool responses."""
    MARKDOWN = "markdown"
    JSON = "json"

class SearchDocsInput(BaseModel):
    """Input model for searching FinOps documentation."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    query: str = Field(..., description="Search query string, e.g., 'What is cloud sustainability?'", min_length=2, max_length=500)
    top_k: int = Field(default=5, description="Number of results to return", ge=1, le=20)
    source_filter: str | None = Field(default=None, description="Optional URL prefix filter to scope results.")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output format")

class ListSourcesInput(BaseModel):
    """Input model for listing FinOps sources."""
    model_config = ConfigDict(validate_assignment=True)

    limit: int = Field(default=20, description="Maximum results to return", ge=1, le=100)
    offset: int = Field(default=0, description="Number of results to skip for pagination", ge=0)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output format")

class GetPageInput(BaseModel):
    """Input model for retrieving a single FinOps page."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    url: str = Field(..., description="The exact URL of the page to retrieve.")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output format")

class BatchGetPagesInput(BaseModel):
    """Input model for retrieving multiple FinOps pages."""
    model_config = ConfigDict(validate_assignment=True)

    urls: list[str] = Field(..., description="List of exact URLs to retrieve", min_length=1, max_length=20)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output format")

class TriggerCrawlInput(BaseModel):
    """Input model for triggering a URL crawl."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    url: str = Field(..., description="The URL to crawl.")
    depth: int = Field(default=2, description="How many levels of links to follow", ge=0, le=5)
    response_format: ResponseFormat = Field(default=ResponseFormat.JSON, description="Output format")

# ── Shared utilities ─────────────────────────────────────────────────────────

def _format_error(msg: str, response_format: ResponseFormat) -> str:
    """Format errors based on requested format."""
    if response_format == ResponseFormat.JSON:
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
def finops_search_docs(params: SearchDocsInput) -> str:
    """Search for documentation about FinOps concepts, frameworks, and practices.

    This tool semantic searches the indexed FinOps Foundation documentation and 
    returns matching chunks of text along with their source URLs.
    """
    from finops_mcp.embeddings import get_query_embedding
    from finops_mcp.vector_store import search

    try:
        query_embedding = get_query_embedding(
            params.query, config.GCP_PROJECT_ID, config.GCP_LOCATION
        )
        results = search(
            query_embedding=query_embedding,
            collection_name=config.FIRESTORE_COLLECTION,
            top_k=params.top_k,
            source_filter=params.source_filter,
        )

        if not results:
            return _format_error("No results found. The collection may be empty.", params.response_format)

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"results": results}, indent=2)

        # Markdown formatting
        lines = [f"# Search Results: '{params.query}'", ""]
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
        return _format_error(str(e), params.response_format)


@mcp.tool(
    name="finops_list_sources",
    annotations={
        "title": "List Indexed FinOps Sources",
        "readOnlyHint": True,
        "openWorldHint": False
    }
)
def finops_list_sources(params: ListSourcesInput) -> str:
    """List all crawled FinOps documentation source URLs with pagination.
    """
    from finops_mcp.vector_store import list_sources

    try:
        # We pass limit and offset down to the datastore
        sources_data = list_sources(config.FIRESTORE_COLLECTION, limit=params.limit, offset=params.offset)
        
        if not sources_data.get("items"):
            return _format_error("No sources indexed yet.", params.response_format)

        if params.response_format == ResponseFormat.JSON:
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
        return _format_error(str(e), params.response_format)


@mcp.tool(
    name="finops_get_page",
    annotations={
        "title": "Get FinOps Page Content",
        "readOnlyHint": True,
        "openWorldHint": False
    }
)
def finops_get_page(params: GetPageInput) -> str:
    """Retrieve the full text content of a single FinOps document by URL."""
    from finops_mcp.vector_store import get_page

    try:
        result = get_page(params.url, config.FIRESTORE_COLLECTION)
        if result is None:
            return _format_error(f"Page not found: {params.url}", params.response_format)

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(result, indent=2, default=str)

        # Markdown formatting
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
        return _format_error(str(e), params.response_format)


@mcp.tool(
    name="finops_batch_get_pages",
    annotations={
        "title": "Batch Get FinOps Pages",
        "readOnlyHint": True,
        "openWorldHint": False
    }
)
def finops_batch_get_pages(params: BatchGetPagesInput) -> str:
    """Retrieve the full text content of up to 20 FinOps documents in a single call."""
    from finops_mcp.vector_store import get_page

    try:
        results = []
        for url in params.urls:
            page = get_page(url, config.FIRESTORE_COLLECTION)
            if page:
                results.append(page)
            else:
                results.append({"url": url, "error": "Page not found"})

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"pages": results}, indent=2, default=str)

        # Markdown
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
        return _format_error(str(e), params.response_format)


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
def finops_trigger_crawl(params: TriggerCrawlInput) -> str:
    """Crawl and index a custom URL into the FinOps documentation store."""
    from finops_mcp.crawler import crawl_url

    try:
        result = asyncio.run(crawl_url(params.url, max_depth=params.depth, skip_existing=False))
        if params.response_format == ResponseFormat.JSON:
            return json.dumps(result, indent=2, default=str)
            
        return (
            f"**Crawl Complete**\n"
            f"- Pages crawled: {result.get('pages_crawled', 0)}\n"
            f"- Chunks upserted: {result.get('chunks_upserted', 0)}\n"
            f"- Duration: {result.get('duration_seconds', 0)}s"
        )
    except Exception as e:
        logger.exception("Error triggering crawl")
        return _format_error(str(e), params.response_format)


# ── Entrypoint ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("Starting FinOps MCP Server (transport=%s)", config.MCP_TRANSPORT)

    if config.MCP_TRANSPORT == "streamable-http":
        mcp.run(
            transport="streamable-http",
            host="0.0.0.0",
            port=config.PORT,
            stateless_http=True,
        )
    else:
        mcp.run(transport="stdio")
