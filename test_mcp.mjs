import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { SSEClientTransport } from "@modelcontextprotocol/sdk/client/sse.js";
async function run() {
    console.log("Connecting...");
    const transport = new SSEClientTransport(new URL("https://mcp.aquaticrabbit.tech/sse"));
    const client = new Client({ name: "test-client", version: "1.0.0" }, { capabilities: {} });
    await client.connect(transport);
    console.log("Connected!");
    const info = await client.request({ method: "initialize", params: { protocolVersion: "2024-11-05", capabilities: {}, clientInfo: { name: "test", version: "1.0" } } }, Object);
    console.log(info);
}
run().catch(console.error);
