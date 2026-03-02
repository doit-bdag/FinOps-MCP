"""Configuration — loads env vars with dotenv, exposes constants."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env in local dev; on Cloud Run these are injected via --set-env-vars
load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)


# ── Google Cloud ──────────────────────────────────────────────────────────────
GCP_PROJECT_ID: str = os.getenv("GCP_PROJECT_ID", "bdag-playground")
GCP_LOCATION: str = os.getenv("GCP_LOCATION", "us-west1")

# ── Firestore ─────────────────────────────────────────────────────────────────
FIRESTORE_COLLECTION: str = os.getenv("FIRESTORE_COLLECTION", "finops_chunks")
FIRESTORE_DATABASE: str = os.getenv("FIRESTORE_DATABASE", "finops-mcp")
FIRESTORE_FOCUS_COLLECTION: str = os.getenv("FIRESTORE_FOCUS_COLLECTION", "finops_focus_columns")
FIRESTORE_TERMS_COLLECTION: str = os.getenv("FIRESTORE_TERMS_COLLECTION", "finops_terms")

# ── Transport ─────────────────────────────────────────────────────────────────
MCP_TRANSPORT: str = os.getenv("MCP_TRANSPORT", "stdio")
PORT: int = int(os.getenv("PORT", "8080"))

# ── Crawl settings ────────────────────────────────────────────────────────────
CRAWL_MAX_DEPTH: int = int(os.getenv("CRAWL_MAX_DEPTH", "3"))
CRAWL_CONCURRENT_PAGES: int = int(os.getenv("CRAWL_CONCURRENT_PAGES", "5"))
CRAWL_DELAY_MS: int = int(os.getenv("CRAWL_DELAY_MS", "500"))

# ── Seed URLs ─────────────────────────────────────────────────────────────────
SEED_URLS: list[str] = [
    "https://www.finops.org/introduction/what-is-finops/",
    "https://www.finops.org/framework/",
    "https://www.finops.org/framework/domains/",
    "https://www.finops.org/framework/capabilities/",
    "https://www.finops.org/framework/maturity/",
    "https://www.finops.org/focus/",
    "https://www.finops.org/projects/",
    "https://www.finops.org/wg/",
    "https://www.finops.org/insights/",
]

# URL path prefixes to skip during crawling
SKIP_PATTERNS: list[str] = [
    "/events/",
    "/membership/",
    "/job-board/",
    "/login/",
]

# Only crawl pages on this domain
ALLOWED_DOMAIN: str = "finops.org"
