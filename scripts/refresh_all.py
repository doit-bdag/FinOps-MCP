"""Unified monthly refresh — re-crawls all FinOps docs and re-ingests structured data.

Orchestrates a full data refresh cycle:
  1. Delete + re-crawl vector docs (finops_chunks)
  2. Re-ingest FOCUS columns and FinOps terms (structured collections)
  3. Log summary stats and exit with appropriate code

Usage:
    uv run python scripts/refresh_all.py              # Full refresh
    uv run python scripts/refresh_all.py --dry-run    # Log planned actions only
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import logging
import sys
import time
from pathlib import Path

# Ensure the src/ package is importable when running as a script
_project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_project_root / "src"))

from finops_mcp import config  # noqa: E402
from finops_mcp.crawler import crawl_url  # noqa: E402
from finops_mcp.vector_store import delete_collection  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


def _load_ingest_focus():
    """Dynamically import ingest_focus.py to access its ingestion functions."""
    spec = importlib.util.spec_from_file_location(
        "ingest_focus", _project_root / "scripts" / "ingest_focus.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


async def _refresh_vector_docs(*, dry_run: bool = False) -> dict:
    """Delete all vector chunks and re-crawl every seed URL."""
    if dry_run:
        logger.info(
            "[DRY RUN] Would delete collection '%s' and re-crawl %d seed URLs at depth=%d",
            config.FIRESTORE_COLLECTION,
            len(config.SEED_URLS),
            config.CRAWL_MAX_DEPTH,
        )
        return {"pages_crawled": 0, "chunks_upserted": 0, "duration_seconds": 0.0}

    logger.info("Deleting collection '%s'...", config.FIRESTORE_COLLECTION)
    deleted = delete_collection(config.FIRESTORE_COLLECTION)
    logger.info("Deleted %d documents", deleted)

    total_pages = 0
    total_chunks = 0
    start = time.time()

    for url in config.SEED_URLS:
        logger.info("Crawling seed: %s", url)
        result = await crawl_url(
            url,
            max_depth=config.CRAWL_MAX_DEPTH,
            skip_existing=False,
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
        "pages_crawled": total_pages,
        "chunks_upserted": total_chunks,
        "duration_seconds": round(duration, 2),
    }


def _refresh_structured_data(*, dry_run: bool = False) -> dict:
    """Re-ingest FOCUS column definitions and FinOps terms."""
    if dry_run:
        logger.info(
            "[DRY RUN] Would refresh FOCUS columns in '%s' and terms in '%s'",
            config.FIRESTORE_FOCUS_COLLECTION,
            config.FIRESTORE_TERMS_COLLECTION,
        )
        return {"columns_upserted": 0, "terms_upserted": 0}

    ingest_focus = _load_ingest_focus()
    cols = ingest_focus.ingest_focus_columns(refresh=True)
    terms = ingest_focus.ingest_terms(refresh=True)
    return {"columns_upserted": cols, "terms_upserted": terms}


async def refresh_all(*, dry_run: bool = False) -> dict:
    """Run the complete monthly refresh cycle.

    Returns a summary dict with stats from both pipelines.
    """
    start = time.time()

    logger.info("=" * 60)
    logger.info("MONTHLY REFRESH — %s", "DRY RUN" if dry_run else "LIVE")
    logger.info("=" * 60)

    # Phase 1: Vector docs (crawl + embed)
    logger.info("Phase 1/2: Refreshing vector documentation...")
    vector_stats = await _refresh_vector_docs(dry_run=dry_run)

    # Phase 2: Structured data (FOCUS columns + terms)
    logger.info("Phase 2/2: Refreshing structured data...")
    structured_stats = _refresh_structured_data(dry_run=dry_run)

    duration = time.time() - start

    summary = {
        **vector_stats,
        **structured_stats,
        "total_duration_seconds": round(duration, 2),
        "dry_run": dry_run,
    }

    logger.info("=" * 60)
    logger.info("REFRESH COMPLETE")
    logger.info("  Pages crawled:    %d", summary["pages_crawled"])
    logger.info("  Chunks upserted:  %d", summary["chunks_upserted"])
    logger.info("  Columns upserted: %d", summary["columns_upserted"])
    logger.info("  Terms upserted:   %d", summary["terms_upserted"])
    logger.info("  Total duration:   %.1fs", summary["total_duration_seconds"])
    logger.info("=" * 60)

    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Full monthly refresh of FinOps MCP data (vector docs + structured data)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log what would be done without modifying any data",
    )
    args = parser.parse_args()

    try:
        asyncio.run(refresh_all(dry_run=args.dry_run))
    except Exception:
        logger.exception("Monthly refresh failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
