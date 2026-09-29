"""MCP client -> a locally self-hosted Notion MCP server.

Notion's HOSTED remote MCP server (mcp.notion.com) requires a full OAuth
flow - real setup friction you don't need this close to a deadline. Instead
this spawns the open-source server locally as a subprocess and talks to it
over stdio, authenticated with a plain Notion integration token:
https://github.com/makenotion/notion-mcp-server

Requires Node/npx installed locally.

Setup:
  1. https://www.notion.so/my-integrations -> create an internal integration,
     copy its token (starts with "ntn_" or "secret_").
  2. In Notion, open the specific page/database you want Loopline to write
     to, click "..." -> Connections -> connect your integration. The
     integration can only see pages you've explicitly connected it to.
"""

from __future__ import annotations

import json
import os
import platform

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

# Confirmed by inspecting the live server: it names tools after the real
# Notion REST endpoints (API-post-page = POST /v1/pages). The others stay
# as fallbacks in case a future server version renames it again.
CREATE_PAGE_CANDIDATES = ("API-post-page", "create_page", "pages_create", "notion_create_pages")


async def _find_tool(session: ClientSession, candidates: tuple[str, ...]) -> str:
    listed = await session.list_tools()
    available = {t.name for t in listed.tools}
    for candidate in candidates:
        if candidate in available:
            return candidate
    raise RuntimeError(
        f"None of {candidates} were found on the Notion MCP server. "
        f"Tools it actually exposes: {sorted(available)}. "
        "Add the right one to CREATE_PAGE_CANDIDATES in notion_client.py."
    )


def _server_params() -> StdioServerParameters:
    token = os.environ["NOTION_TOKEN"]
    headers = {"Authorization": f"Bearer {token}", "Notion-Version": "2022-06-28"}
    # Windows doesn't resolve bare "npx" the way a shell would - needs the
    # .cmd wrapper explicitly, or subprocess spawning fails with WinError 2.
    npx_command = "npx.cmd" if platform.system() == "Windows" else "npx"
    return StdioServerParameters(
        command=npx_command,
        args=["-y", "@notionhq/notion-mcp-server"],
        env={**os.environ, "OPENAPI_MCP_HEADERS": json.dumps(headers)},
    )


async def create_page(parent_page_id: str, title: str, content: str) -> dict:
    """Create a real Notion page under parent_page_id and return {"url": ..., "raw": ...}."""
    async with stdio_client(_server_params()) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tool_name = await _find_tool(session, CREATE_PAGE_CANDIDATES)
            result = await session.call_tool(
                tool_name,
                {
                    # Explicit "type" discriminator - the schema in your
                    # screenshots looked strict (additionalProperties: false),
                    # so match Notion's documented shape exactly rather than
                    # relying on it being inferred.
                    "parent": {"type": "page_id", "page_id": parent_page_id},
                    "properties": {"title": {"title": [{"text": {"content": title}}]}},
                    "children": [
                        {
                            "object": "block",
                            "type": "paragraph",
                            "paragraph": {"rich_text": [{"text": {"content": content}}]},
                        }
                    ],
                },
            )
            raw = [getattr(block, "text", str(block)) for block in result.content]
            # The real response is Notion's page object JSON, which includes
            # a "url" field - pull it out if present.
            url = None
            for text in raw:
                try:
                    data = json.loads(text)
                    if isinstance(data, dict) and data.get("url"):
                        url = data["url"]
                        break
                except (json.JSONDecodeError, TypeError):
                    continue
            return {"url": url, "raw": raw}


if __name__ == "__main__":
    # Isolated test - run BEFORE wiring Notion into the full pipeline.
    import asyncio
    import sys

    sys.path.insert(0, ".")
    from lib import load_env, required  # noqa: E402

    load_env()
    required("NOTION_TOKEN", "create an internal integration at notion.so/my-integrations")
    if len(sys.argv) < 2:
        sys.exit(
            "Usage: python -m processor.mcp_clients.notion_client <parent_page_id>\n"
            "(the id of a page you've connected your integration to)"
        )
    result = asyncio.run(
        create_page(
            sys.argv[1],
            title="Loopline test page - safe to delete",
            content="Created by notion_client.py's isolated test.",
        )
    )
    print(result)