"""FastMCP server — defines MCP tools, switches between stdio and streamable-http."""

from __future__ import annotations

import asyncio
import logging
import sys

from fastmcp import FastMCP

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
    name="finops-docs",
    instructions=(
        "A server that provides semantic search and retrieval over "
        "FinOps Foundation documentation (finops.org). Use search_finops_docs "
        "for questions, list_finops_sources to browse available pages, and "
        "get_finops_page for full page text."
    ),
    version="0.1.0",
)


# ── Startup check ────────────────────────────────────────────────────────────
def _check_collection() -> bool:
    """Warn if the Firestore collection is empty (no data ingested yet)."""
    from finops_mcp.vector_store import collection_is_empty

    if collection_is_empty(config.FIRESTORE_COLLECTION):
        logger.warning(
            "Firestore collection '%s' is empty. "
            "Run 'python scripts/ingest.py' to populate it.",
            config.FIRESTORE_COLLECTION,
        )
        return False
    return True


# ── MCP Tools ─────────────────────────────────────────────────────────────────


@mcp.tool
def search_finops_docs(
    query: str,
    top_k: int = 5,
    source_filter: str | None = None,
) -> list[dict]:
    """Use this tool to find documentation about FinOps concepts, frameworks, and practices.

    This tool returns chunks of text, titles, and URLs for matching documents.
    If the returned chunks are not detailed enough to answer the user's question, 
    use `get_finops_page` or `batch_get_finops_pages` with the `url` from this 
    tool's output to retrieve the full document content.

    Args:
        query: Required. The raw query string, such as "What is cloud sustainability?"
        top_k: Number of results to return (1-20, default 5).
        source_filter: Optional URL prefix filter to scope results.
    """
    from finops_mcp.embeddings import get_query_embedding
    from finops_mcp.vector_store import search

    top_k = max(1, min(top_k, 20))

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
        return [{"message": "No results found. The collection may be empty — run ingestion first."}]

    # Format results for LLM consumption
    formatted = []
    for r in results:
        formatted.append(
            {
                "text": r.get("text", ""),
                "url": r.get("url", ""),
                "title": r.get("title", ""),
                "section_header": r.get("section_header", ""),
                "similarity_score": r.get("similarity_score"),
            }
        )
    return formatted


@mcp.tool
def list_finops_sources() -> list[dict]:
    """List all crawled FinOps documentation sources.

    Returns:
        List of {url, title, chunk_count, crawled_at} for each indexed page.
    """
    from finops_mcp.vector_store import list_sources

    sources = list_sources(config.FIRESTORE_COLLECTION)
    if not sources:
        return [{"message": "No sources indexed yet. Run ingestion first."}]

    # Convert datetime to string for JSON serialization
    for s in sources:
        if s.get("crawled_at"):
            s["crawled_at"] = str(s["crawled_at"])
    return sources


@mcp.tool
def get_finops_page(url: str) -> dict:
    """Use this tool to retrieve the full content of a single document.
    The document url should be obtained from the `url` field of results from a
    call to the `search_finops_docs` tool. If you need to retrieve multiple
    documents, use `batch_get_finops_pages` instead.

    Args:
        url: Required. The exact URL of the page to retrieve.
    """
    from finops_mcp.vector_store import get_page

    result = get_page(url, config.FIRESTORE_COLLECTION)
    if result is None:
        return {"error": f"Page not found: {url}"}

    if result.get("crawled_at"):
        result["crawled_at"] = str(result["crawled_at"])
    return result


@mcp.tool
def batch_get_finops_pages(urls: list[str]) -> list[dict]:
    """Use this tool to retrieve the full content of up to 20 documents in a
    single call. The document urls should be obtained from the `url` field
    of results from a call to the `search_finops_docs` tool. Use this tool
    instead of calling `get_finops_page` multiple times to fetch multiple documents.

    Args:
        urls: Required. The list of exact URLs of the pages to retrieve. A maximum of 20 documents can be retrieved.
    """
    from finops_mcp.vector_store import get_page

    results = []
    for url in urls[:20]:
        page = get_page(url, config.FIRESTORE_COLLECTION)
        if page:
            if page.get("crawled_at"):
                page["crawled_at"] = str(page["crawled_at"])
            results.append(page)
        else:
            results.append({"error": f"Page not found: {url}"})
    return results


@mcp.tool
def trigger_crawl(url: str, depth: int = 2) -> dict:
    """Crawl and index a URL into the FinOps documentation store.

    Args:
        url: The URL to crawl.
        depth: How many levels of links to follow (default 2).

    Returns:
        {pages_crawled, chunks_upserted, duration_seconds}
    """
    from finops_mcp.crawler import crawl_url

    depth = max(0, min(depth, 5))

    result = asyncio.run(crawl_url(url, max_depth=depth, skip_existing=False))
    return result


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
