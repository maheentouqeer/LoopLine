import asyncio, json, sys
sys.path.insert(0, ".")
from lib import load_env
from processor.mcp_clients.notion_client import _server_params
from mcp import ClientSession
from mcp.client.stdio import stdio_client

async def main():
    load_env()
    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            for t in tools.tools:
                if "page" in t.name.lower() or "block" in t.name.lower():
                    print("=" * 60)
                    print(t.name)
                    print(t.description)
                    print(json.dumps(t.input_schema, indent=2))

asyncio.run(main())