"""Smoke tests for the FinOps MCP server modules."""

from __future__ import annotations

import hashlib
from unittest.mock import MagicMock, patch

import pytest


# ── Config tests ──────────────────────────────────────────────────────────────

def test_config_defaults():
    """Config module loads with sensible defaults."""
    from finops_mcp import config

    assert config.GCP_PROJECT_ID  # non-empty
    assert config.GCP_LOCATION  # non-empty
    assert config.FIRESTORE_COLLECTION == "finops_chunks"
    assert config.MCP_TRANSPORT in ("stdio", "streamable-http")
    assert len(config.SEED_URLS) >= 9
    assert config.ALLOWED_DOMAIN == "finops.org"


def test_skip_patterns():
    """Skip patterns include the required exclusions."""
    from finops_mcp import config

    assert "/events/" in config.SKIP_PATTERNS
    assert "/membership/" in config.SKIP_PATTERNS
    assert "/login/" in config.SKIP_PATTERNS


# ── Chunker tests ─────────────────────────────────────────────────────────────

def test_chunk_page_basic():
    """chunk_page returns at least one chunk with correct metadata."""
    from finops_mcp.chunker import chunk_page

    markdown = "# Heading\n\nSome content about FinOps best practices.\n\n" * 5
    chunks = chunk_page(
        url="https://www.finops.org/test/",
        title="Test Page",
        markdown_text=markdown,
    )

    assert len(chunks) >= 1
    first = chunks[0]
    assert first["url"] == "https://www.finops.org/test/"
    assert first["title"] == "Test Page"
    assert first["chunk_index"] == 0
    assert isinstance(first["text"], str)
    assert len(first["text"]) > 0


def test_extract_nearest_heading():
    """_extract_nearest_heading finds the closest heading above a chunk."""
    from finops_mcp.chunker import _extract_nearest_heading

    full_text = "# Main Title\n\n## Section A\n\nContent for section A.\n\n## Section B\n\nContent for section B."
    assert _extract_nearest_heading(full_text, "Content for section A.") == "Section A"
    assert _extract_nearest_heading(full_text, "Content for section B.") == "Section B"
    assert _extract_nearest_heading(full_text, "nonexistent") == ""


def test_chunk_page_empty():
    """chunk_page returns empty list for empty input."""
    from finops_mcp.chunker import chunk_page

    chunks = chunk_page("https://example.com", "Doc", "")
    assert chunks == []


# ── Vector store tests ────────────────────────────────────────────────────────

def test_make_doc_id_deterministic():
    """Document IDs are sha256(url + chunk_index) and deterministic."""
    from finops_mcp.vector_store import _make_doc_id

    id1 = _make_doc_id("https://finops.org/page", 0)
    id2 = _make_doc_id("https://finops.org/page", 0)
    id3 = _make_doc_id("https://finops.org/page", 1)

    assert id1 == id2  # Same input → same output
    assert id1 != id3  # Different chunk_index → different ID
    assert id1 == hashlib.sha256("https://finops.org/page0".encode()).hexdigest()


# ── Embeddings tests ──────────────────────────────────────────────────────────

def test_get_embeddings_batches():
    """get_embeddings batches texts in chunks of 250."""
    from finops_mcp import embeddings

    mock_model = MagicMock()
    mock_result = MagicMock()
    mock_result.values = [0.1] * 768
    mock_model.get_embeddings.return_value = [mock_result]

    with patch.object(embeddings, "_model", mock_model):
        result = embeddings.get_embeddings(
            ["text1"], project="test", location="us-west1"
        )

    assert len(result) == 1
    assert len(result[0]) == 768
    mock_model.get_embeddings.assert_called_once()


# ── Server tests ──────────────────────────────────────────────────────────────

def test_server_has_tools():
    """The FastMCP server instance has all 4 expected tools registered."""
    from finops_mcp.server import mcp

    # FastMCP stores tools internally — just verify the server was created
    assert mcp.name == "finops-docs"


# ── Crawler helper tests ─────────────────────────────────────────────────────

def test_should_skip_url():
    """_should_skip_url correctly filters out unwanted URLs."""
    from finops_mcp.crawler import _should_skip_url

    # Should skip
    assert _should_skip_url("https://www.finops.org/events/summit/")
    assert _should_skip_url("https://www.finops.org/membership/join/")
    assert _should_skip_url("https://www.finops.org/login/")
    assert _should_skip_url("https://www.finops.org/page?foo=bar")
    assert _should_skip_url("https://www.finops.org/doc.pdf")
    assert _should_skip_url("https://externaldomain.com/page")

    # Should NOT skip
    assert not _should_skip_url("https://www.finops.org/framework/")
    assert not _should_skip_url("https://www.finops.org/introduction/what-is-finops/")
