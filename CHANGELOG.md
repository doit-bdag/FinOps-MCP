# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]
### Added
- **Structured Data Ingestion**: Added `ingest_focus.py` to parse definitions directly from focus.finops.org into a `finops_focus_columns` Firestore collection, enabling structured validation.
- **Code-Oriented MCP Tools**: 
  - `finops_get_focus_column`: Fetch deep detail for a specific FOCUS column.
  - `finops_normalize_term`: Map informal phrases (like "real cost") to canonical FinOps naming.
  - `finops_check_focus_compliance`: Validate schemas for required/non-standard FOCUS column names.
  - `finops_generate_ide_rules`: Generate IDE rules (e.g., .cursorrules) for proactive project standards.
- **AI Steering Documents**: Created `AGENTS.md`, `CLAUDE.md`, and `FEEDBACKLOOPS.md` to define guidelines making this repository AI-agent friendly and continuously improving. 
- **Production Endpoints**: Configured standard `sse` transport on FastMCP to expose the service properly through `https://mcp.aquaticrabbit.tech/sse`.
### Changed
- **Server Introspection**: Updated `mcp` instructions and all inner tool docstrings to use declarative "agent-reasoning" language (e.g., "Use this BEFORE writing any code...").

## [0.1.0] - 2026-02-26
### Added
- Initial release of the FinOps MCP server featuring RAG semantic search across finops.org.
- Deployment via Cloud Run for secure API accessibility.
