"""Tests for the monthly refresh orchestrator (scripts/refresh_all.py)."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Make scripts/ importable
_project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_project_root / "src"))


def _import_refresh_all():
    """Dynamically import refresh_all.py so it doesn't run main() on import."""
    spec = importlib.util.spec_from_file_location(
        "refresh_all", _project_root / "scripts" / "refresh_all.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── Dry-run tests ─────────────────────────────────────────────────────────────


def test_refresh_all_dry_run_no_side_effects():
    """--dry-run produces stats without touching Firestore or crawling."""
    refresh_all_mod = _import_refresh_all()

    with (
        patch.object(refresh_all_mod, "delete_collection") as mock_delete,
        patch.object(refresh_all_mod, "crawl_url") as mock_crawl,
    ):
        result = asyncio.run(refresh_all_mod.refresh_all(dry_run=True))

    # No side-effect calls
    mock_delete.assert_not_called()
    mock_crawl.assert_not_called()

    # Stats should all be zero
    assert result["pages_crawled"] == 0
    assert result["chunks_upserted"] == 0
    assert result["columns_upserted"] == 0
    assert result["terms_upserted"] == 0
    assert result["dry_run"] is True


# ── Live-path tests (mocked) ─────────────────────────────────────────────────


def test_refresh_all_calls_both_pipelines():
    """refresh_all invokes both vector crawl and structured data refresh."""
    refresh_all_mod = _import_refresh_all()

    mock_crawl_result = {
        "pages_crawled": 5,
        "chunks_upserted": 20,
        "duration_seconds": 10.0,
    }

    mock_ingest_module = MagicMock()
    mock_ingest_module.ingest_focus_columns.return_value = 48
    mock_ingest_module.ingest_terms.return_value = 12

    with (
        patch.object(refresh_all_mod, "delete_collection", return_value=100) as mock_delete,
        patch.object(
            refresh_all_mod, "crawl_url", new_callable=AsyncMock, return_value=mock_crawl_result
        ) as mock_crawl,
        patch.object(
            refresh_all_mod, "_load_ingest_focus", return_value=mock_ingest_module
        ),
    ):
        result = asyncio.run(refresh_all_mod.refresh_all(dry_run=False))

    # Verify delete was called
    mock_delete.assert_called_once()

    # Verify crawl was called for each seed URL
    from finops_mcp import config

    assert mock_crawl.call_count == len(config.SEED_URLS)

    # Verify structured data ingestion was called
    mock_ingest_module.ingest_focus_columns.assert_called_once_with(refresh=True)
    mock_ingest_module.ingest_terms.assert_called_once_with(refresh=True)

    # Verify combined stats
    assert result["pages_crawled"] == 5 * len(config.SEED_URLS)
    assert result["chunks_upserted"] == 20 * len(config.SEED_URLS)
    assert result["columns_upserted"] == 48
    assert result["terms_upserted"] == 12
    assert result["dry_run"] is False


# ── Helper tests ──────────────────────────────────────────────────────────────


def test_load_ingest_focus_exposes_functions():
    """_load_ingest_focus dynamically imports the ingest_focus module."""
    refresh_all_mod = _import_refresh_all()
    ingest_focus = refresh_all_mod._load_ingest_focus()

    assert hasattr(ingest_focus, "ingest_focus_columns")
    assert hasattr(ingest_focus, "ingest_terms")
    assert callable(ingest_focus.ingest_focus_columns)
    assert callable(ingest_focus.ingest_terms)
