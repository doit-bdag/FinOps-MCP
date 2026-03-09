# Unofficial FinOps Foundation Docs MCP Server

## Purpose

A production-ready [MCP](https://modelcontextprotocol.io/) server that seamlessly integrates the [FinOps Foundation](https://www.finops.org/) documentation directly into your AI assistant or IDE (Claude Desktop, Cursor, Antigravity, etc.). 

It acts as a knowledge layer connecting your agent to Google Cloud Firestore Vector Search and Vertex AI Embeddings, ensuring high-quality, up-to-date FinOps context.

## Function (Features)

The server uses **dynamic tool loading** to minimise context-window overhead. Only 3 lightweight meta-tools are injected at session start (~800 tokens instead of ~12k+). Your agent discovers and loads full tool schemas on demand.

### Meta-Tools (always available)

| Tool                | Description                                                 |
| ------------------- | ----------------------------------------------------------- |
| `list_finops_tools` | Discover available tools — names and one-line descriptions  |
| `load_finops_tools` | Load full input schemas for selected tools                  |
| `call_finops_tool`  | Execute any tool by name with arguments matching its schema |

### Underlying Tools (accessed via `call_finops_tool`)

| Tool Name                | Category   | Description                                                 |
| ------------------------ | ---------- | ----------------------------------------------------------- |
| `search_finops_docs`     | search     | Semantic search across FinOps documentation                 |
| `list_finops_sources`    | search     | List all crawled URLs with metadata                         |
| `get_finops_page`        | search     | Get full text of a specific page                            |
| `batch_get_finops_pages` | search     | Get full text of multiple pages at once                     |
| `trigger_finops_crawl`   | crawl      | Crawl and index a URL on demand                             |
| `get_focus_column`       | compliance | Look up a FOCUS spec column definition (fuzzy matched)      |
| `normalize_finops_term`  | compliance | Map informal language to canonical FinOps terminology       |
| `check_focus_compliance` | compliance | Validate column names against the FOCUS spec                |
| `generate_ide_rules`     | generation | Generate IDE rules files pre-loaded with FinOps conventions |

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
## Disclaimer

This project is an independent, community-built tool and is not affiliated with,
endorsed by, sponsored by, or officially connected to the FinOps Foundation or
the Linux Foundation in any way.

All FinOps® terminology, framework definitions, capability descriptions, domain
structures, maturity model content, and FOCUS™ specification materials referenced
or indexed by this tool are the intellectual property of the FinOps Foundation,
a project of the Linux Foundation. This tool accesses publicly available
documentation from finops.org solely to assist developers in understanding and
applying FinOps standards — it does not claim ownership of, nor does it
redistribute, that content.

FinOps® and FOCUS™ are trademarks of the Linux Foundation.

For authoritative FinOps standards, certification, and official guidance, please
visit [finops.org](https://www.finops.org).
