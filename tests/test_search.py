"""Smoke tests for the FinOps MCP server modules."""

from __future__ import annotations

import hashlib
import json
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

def test_server_has_meta_tools():
    """The FastMCP server exposes the 3 meta-tools."""
    from finops_mcp.server import mcp, list_finops_tools, load_finops_tools, call_finops_tool

    assert mcp.name == "finops_mcp"
    assert callable(list_finops_tools)
    assert callable(load_finops_tools)
    assert callable(call_finops_tool)


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


# ── Underlying tool function tests ──────────────────────────────────────────

def test_underlying_tools_importable():
    """Verify that underlying tool functions are still importable from server.py."""
    from finops_mcp.server import (
        finops_search_docs,
        finops_get_focus_column,
        finops_normalize_term,
        finops_check_focus_compliance,
        finops_generate_ide_rules,
    )

    assert callable(finops_search_docs)
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
    """Verify that underlying tools explain *when* an agent should use them."""
    from finops_mcp.server import (
        finops_search_docs,
        finops_get_focus_column,
        finops_normalize_term,
        finops_check_focus_compliance,
        finops_generate_ide_rules,
    )

    tools = [
        finops_search_docs,
        finops_get_focus_column,
        finops_normalize_term,
        finops_check_focus_compliance,
        finops_generate_ide_rules,
    ]

    for tool_fn in tools:
        doc = tool_fn.__doc__.lower()
        assert "use this" in doc or "call this" in doc, f"{tool_fn.__name__} missing agent reasoning hook"


# ── Meta-tool tests ──────────────────────────────────────────────────────────


def test_list_finops_tools_returns_all():
    """list_finops_tools() returns all registered tools."""
    from finops_mcp.server import list_finops_tools
    from finops_mcp.tool_registry import TOOL_REGISTRY

    result = json.loads(list_finops_tools())
    assert len(result) == len(TOOL_REGISTRY)
    names = {t["name"] for t in result}
    assert names == set(TOOL_REGISTRY.keys())


def test_list_finops_tools_by_category():
    """list_finops_tools(category=...) filters correctly."""
    from finops_mcp.server import list_finops_tools

    compliance_tools = json.loads(list_finops_tools(category="compliance"))
    assert len(compliance_tools) > 0
    for t in compliance_tools:
        assert t["category"] == "compliance"

    # Bogus category returns empty list
    empty = json.loads(list_finops_tools(category="nonexistent"))
    assert empty == []


def test_load_finops_tools_returns_schemas():
    """load_finops_tools() returns full schemas for known tools."""
    from finops_mcp.server import load_finops_tools

    result = json.loads(load_finops_tools(["search_finops_docs", "check_focus_compliance"]))

    assert "search_finops_docs" in result
    assert "check_focus_compliance" in result
    assert "input_schema" in result["search_finops_docs"]
    assert "description" in result["search_finops_docs"]
    assert "example" in result["search_finops_docs"]


def test_load_finops_tools_unknown_tool():
    """load_finops_tools() returns error for unknown tool names."""
    from finops_mcp.server import load_finops_tools

    result = json.loads(load_finops_tools(["totally_fake_tool"]))
    assert "totally_fake_tool" in result
    assert "error" in result["totally_fake_tool"]


def test_call_finops_tool_unknown():
    """call_finops_tool() returns error for unknown tool names."""
    from finops_mcp.server import call_finops_tool

    result = json.loads(call_finops_tool("fake_tool", {}))
    assert "error" in result


@patch("finops_mcp.server.finops_normalize_term")
def test_call_finops_tool_dispatch(mock_handler):
    """call_finops_tool() dispatches to the correct handler."""
    from finops_mcp.server import call_finops_tool
    from finops_mcp import tool_registry

    # Reset to force re-bind
    tool_registry._handlers_bound = False

    mock_handler.return_value = json.dumps({"term": "BilledCost"})

    result = call_finops_tool("normalize_finops_term", {"term": "raw cost"})
    mock_handler.assert_called_once_with(term="raw cost")
    assert "BilledCost" in result


# ── Tool registry tests ─────────────────────────────────────────────────────


def test_tool_registry_completeness():
    """Every registry entry has all required metadata keys."""
    from finops_mcp.tool_registry import TOOL_REGISTRY

    required_keys = {"name", "category", "short_description", "full_description",
                     "input_schema", "returns", "example", "handler"}

    for tool_name, entry in TOOL_REGISTRY.items():
        missing = required_keys - set(entry.keys())
        assert not missing, f"Tool '{tool_name}' missing keys: {missing}"


def test_tool_registry_categories():
    """All registry tools have valid categories."""
    from finops_mcp.tool_registry import TOOL_REGISTRY

    valid = {"search", "compliance", "generation", "crawl"}
    for tool_name, entry in TOOL_REGISTRY.items():
        assert entry["category"] in valid, f"Tool '{tool_name}' has invalid category: {entry['category']}"


# ── Underlying tool logic tests (with mocks) ─────────────────────────────────


@patch("finops_mcp.vector_store.list_structured_docs")
def test_check_focus_compliance(mock_list_docs):
    """Test finops_check_focus_compliance identifies missing and non-standard columns."""
    from finops_mcp.server import finops_check_focus_compliance

    mock_list_docs.return_value = [
        {"column_id": "BilledCost", "required": True, "description": "some cost"},
        {"column_id": "ChargeCategory", "required": True, "description": "some cat"},
        {"column_id": "RegionName", "required": False, "description": "some region"},
    ]

    result = json.loads(finops_check_focus_compliance(
        column_names=["BilledCost", "regionname", "FakeColumn", "billed_cost"],
        response_format="json",
    ))

    assert result["recognized_columns"] == 1
    assert result["total_columns_provided"] == 4
    assert result["missing_required"] == ["ChargeCategory"]

    non_standard = result["non_standard_names"]
    assert len(non_standard) == 3

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
    from finops_mcp.server import finops_normalize_term

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
    res = json.loads(finops_normalize_term(term="BilledCost", response_format="json"))
    assert res["term"] == "BilledCost"

    # Test alias match
    res = json.loads(finops_normalize_term(term="raw cost", response_format="json"))
    assert res["term"] == "BilledCost"

    # Test case insensitive
    res = json.loads(finops_normalize_term(term="ACTUAL COST", response_format="json"))
    assert res["term"] == "EffectiveCost"

    # Test unknown
    res = finops_normalize_term(term="Fake Term", response_format="json")
    assert "error" in json.loads(res)
