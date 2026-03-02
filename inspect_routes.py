from finops_mcp.server import mcp

app = mcp._create_mcp_server()
try:
    routes = getattr(app, "routes", [])
    for r in routes:
        print(f"Route: {getattr(r, 'path', 'none')} Methods: {getattr(r, 'methods', 'none')}")
except Exception as e:
    print(f"Error inspecting routes: {e}")

try:
    from fastmcp.utilities.types import WebhookBase
    
    # Try creating the streamable http app
    from fastmcp.transports.streamable_http import StreamableHTTPTransport
    print("Testing StreamableHTTPTransport setup...")
    t = StreamableHTTPTransport(stateless=False)
    # the Starlette app is usually generated somehow
    print("Transport:", t)
except Exception as e:
    print("Failed streamable check", e)

