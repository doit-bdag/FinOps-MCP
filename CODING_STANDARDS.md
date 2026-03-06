# FinOps MCP Coding Standards

This document establishes the technical conventions and workflow standards for contributing to the FinOps MCP Server. Because this repository actively employs AI coding tools (Claude Code, Cursor) and provides logic *for* AI coding tools, our standards bridge human rules and AI steering documents.

## 1. AI Co-Pilot Integrations

Our workflow leverages declarative AI alignment rules to maintain a consistently high-quality development cycle.

- **[AGENTS.md](./AGENTS.md) & [CLAUDE.md](./CLAUDE.md)**: AI assistants must parse these files to understand the "whys" and "whens" of invoking the MCP's endpoints. Be sure that tools maintain declarative docstrings (e.g. `Use this BEFORE...`) meant specifically for AI consumption.
- **[FEEDBACKLOOPS.md](./FEEDBACKLOOPS.md)**: Any new terminology identified as failing normalization or broken schemas must be fed back into the parsing logic using the steps outlined here. **Read this before submitting feature branches.** Use `gh pr create` via the GitHub CLI for all pull requests.
- **[CHANGELOG.md](./CHANGELOG.md)**: Every substantive change needs an entry under `[Unreleased]` following the *Keep a Changelog* standard.

## 2. Python Architecture

This project is built using Python 3.11+ and `FastMCP`.

- **Package Management:** Use `uv`. To run things use `uv run python script.py` or `uv run pytest`.
- **Tool Creation:** All agent-tools must be declared formally using FastMCP tools. Every tool requires a robust docstring that explains *when* an AI agent should select it over other tools. Input options must be strongly typed using Pydantic Models for fast schema export.
- **Line Length & Formatting:** We use `ruff` to lint Python files. Ensure you run the formatting tests before merging.

Because this MCP serves as the canonical source of truth for cloud financials:

1. **Never hardcode costs data**. Always retrieve canonical definitions from the `finops_terms` and `finops_focus_columns` Firestore collections or the vector-search embeddings.
2. **Follow FOCUS Specs**. When creating or migrating data schemas that involve spend, validate the schemas via the `finops_check_focus_compliance` tool logic.

All tests are implemented using `pytest`.

- **Location:** Code resides in `/src/finops_mcp/` and tests mirror them in `/tests/`.
- **Coverage:** Aim for total functional coverage. Because we leverage FastMCP, explicitly invoke Python unit test asserts on the function `__doc__` properties, specifically verifying that the AI reasoning strings remain intact (`test_tool_descriptions_mention_when_to_use`).

## 5. GitHub Operations

All interactions with GitHub **must** use the GitHub CLI (`gh`). Never use the web UI or raw API calls when the CLI can do the job.

- **Pull Requests:** `gh pr create`, `gh pr merge`, `gh pr view`, `gh pr checks`.
- **Issues:** `gh issue create`, `gh issue list`, `gh issue close`.
- **Secrets:** `gh secret set` for configuring repository or environment secrets.
- **Releases:** `gh release create` for tagging and publishing new versions.
- **Workflow Dispatch:** `gh workflow run <workflow>.yml` to manually trigger GitHub Actions.
- **Repository Settings:** `gh repo edit` for description, visibility, and feature toggles.

By intertwining human development guidelines with robust AI rulesets like `FEEDBACKLOOPS.md` and `AGENTS.md`, we ensure zero-friction iteration when maintaining this MCP backend.
