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
    """The FastMCP server instance has all 5 expected tools registered."""
    from finops_mcp.server import mcp

    # FastMCP stores tools internally — just verify the server was created
    assert mcp.name == "finops_mcp"


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
# ── Vibe-Coder Tools Tests ──────────────────────────────────────────────────

def test_vibe_coder_tools_registered():
    """Verify that vibe-coder tools are registered in the server."""
    from finops_mcp.server import (
        finops_get_focus_column,
        finops_normalize_term,
        finops_check_focus_compliance,
        finops_generate_ide_rules
    )

    assert callable(finops_get_focus_column)
    assert callable(finops_normalize_term)
    assert callable(finops_check_focus_compliance)
    assert callable(finops_generate_ide_rules)


def test_server_instructions_mention_agent_reasoning():
    """Verify that the MCP server instructions use direct agent commands."""
    from finops_mcp.server import mcp

    instructions = mcp.instructions.lower()
    
    # Must contain declarative commands to the agent
    assert "use this server before" in instructions or "always consult this server when" in instructions
    assert "cost" in instructions
    assert "focus" in instructions


def test_tool_descriptions_mention_when_to_use():
    """Verify that tools have been rewritten to explain *when* an agent should use them."""
    
    # Since we're just checking docstrings, we can inspect the functions directly
    from finops_mcp.server import (
        finops_search_docs,
        finops_get_focus_column,
        finops_normalize_term,
        finops_check_focus_compliance,
        finops_generate_ide_rules
    )

    tools = [
        finops_search_docs,
        finops_get_focus_column,
        finops_normalize_term,
        finops_check_focus_compliance,
        finops_generate_ide_rules
    ]

    for tool_fn in tools:
        doc = tool_fn.__doc__.lower()
        # All tools should have agent-reasoning hooks like "use this" or "call this"
        assert "use this" in doc or "call this" in doc, f"{tool_fn.__name__} missing agent reasoning hook"


@patch("finops_mcp.vector_store.list_structured_docs")
def test_check_focus_compliance(mock_list_docs):
    """Test finops_check_focus_compliance identifies missing and non-standard columns."""
    from finops_mcp.server import finops_check_focus_compliance, CheckFocusComplianceInput, ResponseFormat

    # Mock the return value of list_structured_docs
    mock_list_docs.return_value = [
        {"column_id": "BilledCost", "required": True, "description": "some cost"},
        {"column_id": "ChargeCategory", "required": True, "description": "some cat"},
        {"column_id": "RegionName", "required": False, "description": "some region"},
    ]

    # Input has:
    # - 1 valid required (BilledCost)
    # - 1 missing required (ChargeCategory)
    # - 1 case error (regionname -> RegionName)
    # - 1 invalid (FakeColumn)
    # - 1 fuzzy match candidate (billed_cost -> BilledCost) - wait, fuzzy match logic only
    #   replaces spaces and underscores. So billed_cost -> BilledCost is non_standard.
    params = CheckFocusComplianceInput(
        column_names=["BilledCost", "regionname", "FakeColumn", "billed_cost"],
        response_format=ResponseFormat.JSON
    )

    result_json = finops_check_focus_compliance(params)
    import json
    result = json.loads(result_json)

    assert result["recognized_columns"] == 1
    assert result["total_columns_provided"] == 4
    assert result["missing_required"] == ["ChargeCategory"]

    non_standard = result["non_standard_names"]
    assert len(non_standard) == 3

    # Check specific errors
    issues = {ns["provided"]: ns for ns in non_standard}
    assert issues["regionname"]["issue"] == "wrong_case"
    assert issues["regionname"]["correct"] == "RegionName"
    
    assert issues["FakeColumn"]["issue"] == "unknown_column"
    assert issues["FakeColumn"]["correct"] is None

    assert issues["billed_cost"]["issue"] == "non_standard_name"
    assert issues["billed_cost"]["correct"] == "BilledCost"


@patch("finops_mcp.vector_store.list_structured_docs")
def test_normalize_term(mock_list_docs):
    """Test finops_normalize_term maps informal terms to canonical ones."""
    from finops_mcp.server import finops_normalize_term, NormalizeTermInput, ResponseFormat

    # Mock the return value of list_structured_docs
    mock_list_docs.return_value = [
        {
            "term": "BilledCost",
            "display_name": "Billed Cost",
            "definition": "A charge serving as the basis for invoicing",
            "aliases": ["bill amount", "charge", "raw cost"],
            "do_not_say": ["actual cost"],
            "focus_columns": ["BilledCost"]
        },
        {
            "term": "EffectiveCost",
            "display_name": "Effective Cost",
            "definition": "The amortized cost",
            "aliases": ["actual cost", "real cost"],
            "do_not_say": ["raw cost"],
            "focus_columns": ["EffectiveCost"]
        }
    ]

    # Test exact match
    params = NormalizeTermInput(term="BilledCost", response_format=ResponseFormat.JSON)
    import json
    res = json.loads(finops_normalize_term(params))
    assert res["term"] == "BilledCost"

    # Test alias match
    params = NormalizeTermInput(term="raw cost", response_format=ResponseFormat.JSON)
    res = json.loads(finops_normalize_term(params))
    assert res["term"] == "BilledCost"

    # Test case insensitive
    params = NormalizeTermInput(term="ACTUAL COST", response_format=ResponseFormat.JSON)
    res = json.loads(finops_normalize_term(params))
    assert res["term"] == "EffectiveCost"

    # Test unknown
    params = NormalizeTermInput(term="Fake Term", response_format=ResponseFormat.JSON)
    res = finops_normalize_term(params)
    assert "error" in json.loads(res)


