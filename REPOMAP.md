# Repository Map

The FinOps MCP Server codebase is optimized for clarity so both biological engineers and AI agents can rapidly find what they need.

## 🧭 High-Level Overview

```text
FinOps-MCP
├── src/finops_mcp/     # Core Business Logic & Endpoints
├── scripts/            # Database Caching & Content Scrapers
├── tests/              # Pytest Functional Test Suite
├── infrastructure/     # Deployment Configs (Cloud Run/Docker/GCP)
└── AI Steering/        # Core Agent Files (AGENTS.md, FEEDBACKLOOPS, etc)
```

## 📁 Detailed Directory Map

### Core Application (`src/finops_mcp/`)

Contains the primary FastMCP router and all dependent API operations.

- `server.py`: The entry point. Registers all MCP tools (`finops_search_docs`, `finops_normalize_term`, etc.) and mounts the SSE HTTP endpoint.
- `vector_store.py`: Abstractions connecting the backend to Google Cloud Firestore, managing queries for semantic chunks and structured FOCUS documents.
- `embeddings.py`: Wraps Vertex AI's text-embedding models used to vector-map the documentation.
- `chunker.py`: Logic to recursively digest HTML elements into cleanly defined semantic text boundaries.
- `crawler.py`: Custom web crawling tools tracking FinOps.org layouts.
- `config.py`: Core environment and standard definition imports.

### Database Population (`scripts/`)

- `ingest_focus.py`: Reads the live `focus.finops.org` spec and commits canonical definitions into structured database tables for compliance validations.
- `ingest.py`: Performs standard HTML page semantic-caching and vector generation for global searches.

### AI Control Documents (Root)

Files used directly by IDE plugins (e.g. Cursor, Claude) to format and limit how code is generated.

- `AGENTS.md` / `CLAUDE.md`: The immediate entry-point instruction guidelines dictating *how* AI connects to our systems.
- `FEEDBACKLOOPS.md`: Procedures orchestrating continuous-improvement mechanisms that ensure developers (human and AI) learn from edge cases.
- `CODING_STANDARDS.md`: Technical formatting rules and testing criteria.

### Testing (`tests/`)

- `test_search.py`: Validates that AI-reasoning properties exist in the `server.py` implementation, ensuring tools correctly process test phrases (e.g. mapping "actual cost" to "EffectiveCost").

### Infrastructure & Deployment (Root)

- `cloudbuild.yaml`: The Google Cloud Build configuration that packages the python environment and initiates the Cloud Run push.
- `pyproject.toml` / `uv.lock`: Project package dependencies, executed via Astral limits.
- `Dockerfile`: Defines the system image logic.
- `mcp_config.json` (Note: Often configured in the IDE locally): The map connecting your host IDE (Cursor/Claude) to the `https://mcp.aquaticrabbit.tech/sse` remote interface.
