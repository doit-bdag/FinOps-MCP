"""Standalone ingestion CLI — crawl FinOps docs into Firestore."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time

# Ensure the src/ package is importable when running as a script
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "src"))

from finops_mcp import config  # noqa: E402
from finops_mcp.crawler import crawl_url  # noqa: E402
from finops_mcp.vector_store import delete_collection  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


async def ingest_all(
    urls: list[str],
    max_depth: int,
    skip_existing: bool = True,
) -> dict:
    """Crawl all seed URLs and return aggregate stats."""
    total_pages = 0
    total_chunks = 0
    start = time.time()

    for url in urls:
        logger.info("Starting crawl for seed: %s", url)
        result = await crawl_url(
            url,
            max_depth=max_depth,
            skip_existing=skip_existing,
        )
        total_pages += result["pages_crawled"]
        total_chunks += result["chunks_upserted"]
        logger.info(
            "Seed %s done: %d pages, %d chunks",
            url,
            result["pages_crawled"],
            result["chunks_upserted"],
        )

    duration = time.time() - start
    return {
        "total_pages": total_pages,
        "total_chunks": total_chunks,
        "duration_seconds": round(duration, 2),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Ingest FinOps Foundation docs into Firestore vector store"
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Delete all existing chunks and re-ingest from scratch",
    )
    parser.add_argument(
        "--url",
        type=str,
        default=None,
        help="Re-ingest a single URL instead of all seeds",
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=None,
        help=f"Max crawl depth (default: {config.CRAWL_MAX_DEPTH})",
    )
    args = parser.parse_args()

    max_depth = args.depth if args.depth is not None else config.CRAWL_MAX_DEPTH

    if args.refresh:
        logger.info(
            "Refreshing: deleting all docs in '%s'...",
            config.FIRESTORE_COLLECTION,
        )
        deleted = delete_collection(config.FIRESTORE_COLLECTION)
        logger.info("Deleted %d documents", deleted)

    if args.url:
        urls = [args.url]
        skip_existing = False  # Always re-crawl when a specific URL is given
    else:
        urls = config.SEED_URLS
        skip_existing = not args.refresh

    logger.info(
        "Ingesting %d URLs at depth=%d (skip_existing=%s)",
        len(urls),
        max_depth,
        skip_existing,
    )

    result = asyncio.run(ingest_all(urls, max_depth, skip_existing))

    logger.info(
        "Ingestion complete: %d pages, %d chunks in %.1fs",
        result["total_pages"],
        result["total_chunks"],
        result["duration_seconds"],
    )


if __name__ == "__main__":
    main()
