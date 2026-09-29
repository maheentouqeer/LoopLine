import asyncio, json, sys
sys.path.insert(0, ".")
from lib import load_env
from processor.mcp_clients.github_client import GITHUB_MCP_URL
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
import httpx, os

async def main():
    load_env()
    token = os.environ["GITHUB_PAT"]
    http_client = httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"})
    async with streamable_http_client(GITHUB_MCP_URL, http_client=http_client) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            for t in tools.tools:
                if t.name == "issue_write":
                    print(t.name)
                    print(t.description)
                    print(json.dumps(t.input_schema, indent=2))

asyncio.run(main())