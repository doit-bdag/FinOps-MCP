from fastmcp import FastMCP
mcp = FastMCP("test")
try:
    mcp.run(transport="sse", port=61234, host="127.0.0.1")
except Exception as e:
    print(e)
