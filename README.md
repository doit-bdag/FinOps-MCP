# FinOps Foundation Docs MCP Server

A production-ready [MCP](https://modelcontextprotocol.io/) server that crawls, indexes, and exposes the [FinOps Foundation](https://www.finops.org/) documentation as queryable tools for LLM clients (Claude Desktop, Cursor, etc.).

**100% Google Cloud** — Cloud Run + Firestore Vector Search + Vertex AI Embeddings.

## Architecture

```
MCP Client  ──►  Cloud Run (MCP Server)  ──►  Firestore (Vector Store)
                        │
                        ▼
                 Vertex AI (Embeddings)
```

## Quick Start (Local)

```bash
# 1. Authenticate
gcloud auth application-default login

# 2. Copy env vars
cp .env.example .env

# 3. Install
pip install uv
uv pip install -e .

# 4. Run in stdio mode
python -m finops_mcp.server
```

## Ingestion

```bash
# Ingest all seed URLs
python scripts/ingest.py

# Re-ingest everything
python scripts/ingest.py --refresh

# Ingest a single URL
python scripts/ingest.py --url https://www.finops.org/framework/
```

## MCP Tools

| Tool                  | Description                                 |
| --------------------- | ------------------------------------------- |
| `search_finops_docs`  | Semantic search across FinOps documentation |
| `list_finops_sources` | List all crawled URLs with metadata         |
| `get_finops_page`     | Get full text of a specific page            |
| `trigger_crawl`       | Crawl and index a URL on demand             |

## Deploy to Cloud Run

```bash
gcloud run deploy finops-mcp \
  --source . \
  --region us-west1 \
  --project bdag-playground \
  --service-account finops-mcp-sa@bdag-playground.iam.gserviceaccount.com \
  --no-allow-unauthenticated \
  --set-env-vars MCP_TRANSPORT=streamable-http,GCP_PROJECT_ID=bdag-playground,GCP_LOCATION=us-west1,FIRESTORE_COLLECTION=finops_chunks \
  --memory 1Gi --cpu 1 --min-instances 0 --max-instances 5 --timeout 300
```

## Claude Desktop Config (stdio)

```json
{
  "mcpServers": {
    "finops-docs": {
      "command": "uv",
      "args": ["run", "--project", "/path/to/finops-mcp", "python", "-m", "finops_mcp.server"],
      "env": {
        "MCP_TRANSPORT": "stdio",
        "GCP_PROJECT_ID": "bdag-playground",
        "GCP_LOCATION": "us-west1"
      }
    }
  }
}
```

## Claude Desktop Config (Cloud Run via proxy)

```bash
gcloud run services proxy finops-mcp --region us-west1 --port 3000
```

```json
{
  "mcpServers": {
    "finops-docs": {
      "url": "http://localhost:3000/mcp"
    }
  }
}
```
