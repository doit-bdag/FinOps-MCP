import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client

async def test():
    async with sse_client("https://mcp.aquaticrabbit.tech/sse") as streams:
        async with ClientSession(streams[0], streams[1]) as session:
            await session.initialize()
                
            print("\nCalling normalize_term...")
            result = await session.call_tool("finops_normalize_term", {"params": {"term": "actual real cost"}})
            print(f"Result: {result.content[0].text if result.content else 'None'}")

asyncio.run(test())
