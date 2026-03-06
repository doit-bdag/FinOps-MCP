"""Web crawler using crawl4ai with PruningContentFilter for LLM-optimized markdown."""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from typing import Any
from urllib.parse import urlparse

from finops_mcp import config
from finops_mcp.chunker import chunk_page
from finops_mcp.embeddings import get_embeddings
from finops_mcp.vector_store import upsert_chunk, url_exists

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler(sys.stderr))


def _should_skip_url(url: str) -> bool:
    """Check if URL matches skip patterns or is outside allowed domain."""
    parsed = urlparse(url)

    # Domain lock
    if config.ALLOWED_DOMAIN not in parsed.netloc:
        return True

    # Skip patterns
    for pattern in config.SKIP_PATTERNS:
        if pattern in parsed.path:
            return True

    # Skip URLs with query params
    if parsed.query:
        return True

    # Skip non-HTML (PDFs etc.)
    if parsed.path.endswith((".pdf", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".zip")):
        return True

    return False


async def crawl_url(
    url: str,
    max_depth: int = 2,
    skip_existing: bool = True,
) -> dict[str, Any]:
    """Crawl a URL recursively, chunk, embed, and upsert to Firestore.

    Returns: {pages_crawled, chunks_upserted, duration_seconds}
    """
    from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
    from crawl4ai.content_filter_strategy import PruningContentFilter
    from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

    start = time.time()
    pages_crawled = 0
    chunks_upserted = 0
    visited: set[str] = set()
    queue: list[tuple[str, int]] = [(url, 0)]

    md_generator = DefaultMarkdownGenerator(
        content_filter=PruningContentFilter(threshold=0.5),
        options={"ignore_links": False},
    )
    run_config = CrawlerRunConfig(markdown_generator=md_generator)

    async with AsyncWebCrawler() as crawler:
        while queue:
            current_url, depth = queue.pop(0)

            # Hard cap on total pages per crawl invocation
            if pages_crawled >= config.CRAWL_MAX_PAGES:
                logger.info(
                    "Reached CRAWL_MAX_PAGES=%d, stopping crawl of %s",
                    config.CRAWL_MAX_PAGES,
                    url,
                )
                break

            # Normalize URL
            current_url = current_url.rstrip("/")
            if current_url in visited:
                continue
            visited.add(current_url)

            if _should_skip_url(current_url):
                logger.debug("Skipping: %s", current_url)
                continue

            # Skip if already in Firestore (incremental mode)
            if skip_existing and url_exists(current_url, config.FIRESTORE_COLLECTION):
                logger.info("Already indexed, skipping: %s", current_url)
                continue

            logger.info("Crawling: %s (depth=%d)", current_url, depth)

            try:
                result = await crawler.arun(current_url, config=run_config)
            except Exception:
                logger.exception("Failed to crawl: %s", current_url)
                continue

            if not result.success:
                logger.warning(
                    "Crawl failed for %s: %s",
                    current_url,
                    getattr(result, "error_message", "unknown"),
                )
                continue

            pages_crawled += 1

            # Extract markdown — use fit_markdown if available
            markdown_text = ""
            md = result.markdown
            if hasattr(md, "fit_markdown") and md.fit_markdown:
                markdown_text = md.fit_markdown
            elif hasattr(md, "raw_markdown") and md.raw_markdown:
                markdown_text = md.raw_markdown
            elif isinstance(md, str):
                markdown_text = md

            if not markdown_text.strip():
                logger.warning("Empty markdown for %s", current_url)
                continue

            # Extract title
            title = getattr(result, "title", "") or current_url

            # Chunk the page
            chunks = chunk_page(current_url, title, markdown_text)
            if not chunks:
                continue

            # Embed all chunk texts in batch
            texts = [c["text"] for c in chunks]
            embeddings = get_embeddings(
                texts, config.GCP_PROJECT_ID, config.GCP_LOCATION
            )

            # Upsert to Firestore
            for chunk_data, embedding in zip(chunks, embeddings):
                chunk_data["embedding"] = embedding
                upsert_chunk(chunk_data, config.FIRESTORE_COLLECTION)
                chunks_upserted += 1

            logger.info(
                "Indexed %s: %d chunks",
                current_url,
                len(chunks),
            )

            # Discover links for recursive crawling
            if depth < max_depth:
                links = _extract_links(result, current_url)
                for link in links:
                    if link not in visited:
                        queue.append((link, depth + 1))

            # Rate limiting
            await asyncio.sleep(config.CRAWL_DELAY_MS / 1000.0)

    duration = time.time() - start
    return {
        "pages_crawled": pages_crawled,
        "chunks_upserted": chunks_upserted,
        "duration_seconds": round(duration, 2),
    }


def _extract_links(result: Any, base_url: str) -> list[str]:
    """Extract internal links from crawl result."""
    links: list[str] = []
    parsed_base = urlparse(base_url)

    # Try to get links from result metadata
    raw_links = getattr(result, "links", None)
    if raw_links and isinstance(raw_links, dict):
        for link_list in raw_links.values():
            if isinstance(link_list, list):
                for item in link_list:
                    href = item.get("href", "") if isinstance(item, dict) else str(item)
                    if href:
                        links.append(href)
    elif raw_links and isinstance(raw_links, list):
        for item in raw_links:
            href = item.get("href", "") if isinstance(item, dict) else str(item)
            if href:
                links.append(href)

    # Normalize and filter
    normalized: list[str] = []
    for link in links:
        if link.startswith("/"):
            link = f"{parsed_base.scheme}://{parsed_base.netloc}{link}"
        parsed = urlparse(link)
        if config.ALLOWED_DOMAIN in parsed.netloc and not _should_skip_url(link):
            normalized.append(link.rstrip("/"))

    return list(set(normalized))
