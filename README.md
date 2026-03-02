# FinOps Foundation Docs MCP Server

A production-ready [MCP](https://modelcontextprotocol.io/) server that crawls, indexes, and exposes the [FinOps Foundation](https://www.finops.org/) documentation as queryable tools for LLM clients (Claude Desktop, Cursor, etc.).

**100% Google Cloud** — Cloud Run + Firestore Vector Search + Vertex AI Embeddings.

## Architecture

```text
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

| Tool                     | Description                                 |
| ------------------------ | ------------------------------------------- |
| `finops_search_docs`     | Semantic search across FinOps documentation |
| `finops_list_sources`    | List all crawled URLs with metadata         |
| `finops_get_page`        | Get full text of a specific page            |
| `finops_batch_get_pages` | Get full text of multiple pages at once     |
| `finops_trigger_crawl`   | Crawl and index a URL on demand             |

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

## Connecting your MCP Client

The FinOps MCP Server operates securely. There are two ways to connect your agent/IDE, depending on what transport it supports.

### Option 1: Local Stdio Mode (Recommended)

This is the **most robust method** and natively supports **Claude Code, Cursor, Antigravity, and Kiro**.
The server runs locally on your machine but communicates with the centralized Cloud Firestore database and Vertex AI models using your Google Cloud credentials. This guarantees all team members share the same synchronized index.

First, ensure you are authenticated with your `@doit.com` account and your environment is set up:

```bash
gcloud auth application-default login

# Ensure uv is installed and the project is set up
pip install uv
uv pip install -e .
```

Then configure your specific client:

* **Claude Code**:

  ```bash
  claude mcp add finops-mcp uv -- run --project /absolute/path/to/FinOps-MCP python -m finops_mcp.server
  ```

* **Cursor**:
  * Open Cursor Settings > Features > MCP Servers
  * Click **+ Add New**
  * Type: `stdio`
  * Name: `finops-mcp`
  * Command: `uv run --project /absolute/path/to/FinOps-MCP python -m finops_mcp.server`

* **Antigravity**:
  * Add this to your global `~/.gemini/antigravity/mcp_config.json`:

  ```json
  "finops_mcp": {
    "command": "npx",
    "args": [
      "-y",
      "mcp-remote",
      "https://mcp.aquaticrabbit.tech/sse"
    ],
    "env": {}
  }
  ```

* **Kiro**:
  * Add this to Kiro's MCP configuration JSON:

  ```json
  "mcpServers": {
    "finops-mcp": {
      "command": "uv",
      "args": ["run", "--project", "/absolute/path/to/FinOps-MCP", "python", "-m", "finops_mcp.server"]
    }
  }
  ```

### Option 2: Remote Cloud Run Endpoint (SSE)

The Cloud Run service is locked down via IAM exclusively to `domain:doit.com` users. You cannot access it publically without a valid identity token.

To easily bypass complex header injection in your IDE (which many don't natively support), use the `gcloud run services proxy` command. This creates a secure local bridge that automatically attaches your `@doit.com` identity token to all outbound requests.

1. **Start the secure proxy (leave this running in a terminal):**

   ```bash
   gcloud run services proxy finops-mcp --region us-west1 --project bdag-playground --port 3000
   ```

2. **Configure your client:**

   * **Claude Desktop**:
     Update `claude_desktop_config.json`:

     ```json
     {
       "mcpServers": {
         "finops-cloud": {
           "url": "http://localhost:3000/mcp"
         }
       }
     }
     ```

   * **Cursor**:
     * Open Cursor Settings > Features > MCP Servers
     * Click **+ Add New**
     * Type: `sse`
     * Name: `finops-cloud`
     * URL: `http://localhost:3000/mcp`

   * **Antigravity**:
     * Update your `.agent/` configuration or launch command to specify the SSE transport with the proxy URL: `http://localhost:3000/mcp`.
