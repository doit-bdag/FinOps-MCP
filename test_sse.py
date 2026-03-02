import asyncio
import httpx
from mcp import ClientSession

async def main():
    async with httpx.AsyncClient() as client:
        # Start SSE connection
        headers = {"Accept": "text/event-stream"}
        try:
            req = client.build_request("GET", "https://mcp.aquaticrabbit.tech/mcp", headers=headers)
            print(f"Request: {req.url} {req.headers}")
            response = await client.send(req, stream=True)
            print(f"Response status: {response.status_code}")
            print(f"Response headers: {response.headers}")
            # read first few chunks
            count = 0
            async for chunk in response.aiter_text():
                print(f"Chunk: {chunk}")
                count += 1
                if count > 5:
                    break
        except Exception as e:
            print(f"Error: {e}")
            
if __name__ == "__main__":
    asyncio.run(main())
