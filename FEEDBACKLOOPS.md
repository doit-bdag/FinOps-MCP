# AI Feedback Loops

To effectively evolve this repository, we adhere to the following continuous improvement loops when working with AI coding agents:

## 1. Schema & Compliance Feedback
- **Action:** Before committing database schema changes or data pipelines that mention cloud costs, run `finops_check_focus_compliance`.
- **Loop:** If an agent generates code containing invalid structure, it uses the tool to identify what it missed and integrates that feedback directly into its context to fix the types before they are reviewed by a human.

## 2. Terminology Normalization
- **Action:** If a user requests a code change using an unknown terminology (like "my raw billing data"), use `finops_normalize_term`.
- **Loop:** If the API returns an error stating the term is unknown, engineers or agents should add the missing alias mapping to the `finops_terms` ingestion script, running `uv run python scripts/ingest_focus.py` to continuously expand the server's vocabulary.

## 3. Crawler Expansion
- **Action:** When `finops_search_docs` lacks sufficient documentation for a specific inquiry, agents should use the web to find the missing `finops.org` URL and invoke `finops_trigger_crawl`.
- **Loop:** The documentation is added to Firestore, instantly improving future contextual searches across the entire engineering pipeline.

## 4. IDE Constraints
- **Action:** If persistent stylistic errors or non-FOCUS naming conventions show up in Pull Requests, team members should invoke the `finops_generate_ide_rules` tool and drop the output file (`.cursorrules` / `AGENTS.md`) at the root of their repository.
- **Loop:** The generated rules proactively inject constraints into the AI environment *before* poor practices can be drafted.
