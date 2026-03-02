# FinOps Foundation Docs MCP Server

## Purpose

A production-ready [MCP](https://modelcontextprotocol.io/) server that seamlessly integrates the [FinOps Foundation](https://www.finops.org/) documentation directly into your AI assistant or IDE (Claude Desktop, Cursor, Antigravity, etc.).

It acts as a knowledge layer connecting your agent to Google Cloud Firestore Vector Search and Vertex AI Embeddings, ensuring high-quality, up-to-date FinOps context.

## Function (Features)

The server exposes the following tools directly to your AI agent so it can read and navigate the FinOps framework autonomously:

| Tool                     | Description                                 |
| ------------------------ | ------------------------------------------- |
| `finops_search_docs`     | Semantic search across FinOps documentation |
| `finops_list_sources`    | List all crawled URLs with metadata         |
| `finops_get_page`        | Get full text of a specific page            |
| `finops_batch_get_pages` | Get full text of multiple pages at once     |
| `finops_trigger_crawl`   | Crawl and index a URL on demand             |

## Setup Instructions

### 🌐 Option 1: Connect to the Public Cloud Run Server (Recommended)

You can directly connect to the hosted `https://mcp.aquaticrabbit.tech/sse` endpoint. Because many IDEs don't natively translate SSE gracefully into JSON-RPC, the easiest and most robust method is to use the official Node `mcp-remote` proxy.

**Prerequisites:** You must have `Node.js` installed.

* **Claude Desktop**
  Add the following to your `claude_desktop_config.json`:

  ```json
  {
    "mcpServers": {
      "finops_mcp": {
        "command": "npx",
        "args": ["-y", "mcp-remote", "https://mcp.aquaticrabbit.tech/sse"]
      }
    }
  }
  ```

* **Cursor**
  * Open **Cursor Settings > Features > MCP Servers**
  * Click **+ Add New**
  * Type: `command`
  * Name: `finops_mcp`
  * Command: `npx -y mcp-remote https://mcp.aquaticrabbit.tech/sse`

* **Antigravity**
  Add the following to your `~/.gemini/antigravity/mcp_config.json`:

  ```json
  {
    "mcpServers": {
      "finops_mcp": {
        "command": "npx",
        "args": ["-y", "mcp-remote", "https://mcp.aquaticrabbit.tech/sse"]
      }
    }
  }
  ```

---

### 💻 Option 2: Run the Server Locally

If you are developing or prefer to run the server entirely from your own machine, you can run the python server locally in `stdio` mode.

1. **Install uv**

   ```bash
   pip install uv
   ```

2. **Download the project**

   ```bash
   git clone https://github.com/doit-bdag/FinOps-MCP.git
   cd FinOps-MCP
   uv pip install -e .
   ```

3. **Authenticate your Google Cloud Session** (Required for Firestore + Vertex AI access)

   ```bash
   gcloud auth application-default login
   ```

4. **Configure your IDE**
   Add the native local execution command to your MCP client config (e.g., Cursor, Claude Desktop, Antigravity):

   ```json
   {
     "command": "uv",
     "args": ["run", "--project", "/absolute/path/to/FinOps-MCP", "python", "-m", "finops_mcp.server"],
     "env": {
       "MCP_TRANSPORT": "stdio"
     }
   }
   ```
