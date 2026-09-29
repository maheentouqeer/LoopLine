"""MCP client -> GitHub's official remote MCP server.

Server: https://api.githubcopilot.com/mcp/
Auth:   a plain Authorization: Bearer <PAT> header - no OAuth dance.

Confirmed live: issues are created/updated through one consolidated
"issue_write" tool (method: "create" | "update"), not a dedicated
create_issue tool.
"""

from __future__ import annotations

import json
import os

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

GITHUB_MCP_URL = "https://api.githubcopilot.com/mcp/"
CREATE_ISSUE_CANDIDATES = ("issue_write", "create_issue", "issues_create", "create_an_issue")


async def _find_tool(session: ClientSession, candidates: tuple[str, ...]) -> str:
    listed = await session.list_tools()
    available = {t.name for t in listed.tools}
    for candidate in candidates:
        if candidate in available:
            return candidate
    raise RuntimeError(
        f"None of {candidates} were found on the GitHub MCP server. "
        f"Tools it actually exposes: {sorted(available)}. "
        "Add the right one to CREATE_ISSUE_CANDIDATES in github_client.py."
    )


async def create_issue(owner: str, repo: str, title: str, body: str) -> dict:
    """Create a real GitHub issue and return {"url": ..., "raw": ...}."""
    token = os.environ["GITHUB_PAT"]
    http_client = httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"})

    async with streamable_http_client(GITHUB_MCP_URL, http_client=http_client) as (
        read_stream,
        write_stream,
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tool_name = await _find_tool(session, CREATE_ISSUE_CANDIDATES)
            result = await session.call_tool(
                tool_name,
                {"method": "create", "owner": owner, "repo": repo, "title": title, "body": body},
            )
        raw = [getattr(block, "text", str(block)) for block in result.content]

        url = None
        for text in raw:
            try:
                data = json.loads(text)
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(data, dict) and isinstance(data.get("url"), str) and "github.com" in data["url"]:
                url = data["url"]
                break

        if url is None:
            # A successful create always returns a real url (confirmed
            # against the live server). No url means something actually
            # failed - raise so pipeline.py reports it as an error
            # instead of a false "filed".
            raise RuntimeError(f"GitHub did not confirm the issue was created. Raw response: {raw}")

        return {"url": url, "raw": raw}

if __name__ == "__main__":
    import asyncio
    import sys

    sys.path.insert(0, ".")
    from lib import load_env, required  # noqa: E402

    load_env()
    required("GITHUB_PAT", "create a fine-grained PAT scoped to one test repo")
    if len(sys.argv) < 3:
        sys.exit("Usage: python -m processor.mcp_clients.github_client <owner> <repo>")

    result = asyncio.run(
        create_issue(
            sys.argv[1], sys.argv[2],
            title="Loopline test issue - safe to delete",
            body="Created by github_client.py's isolated test. If you see this, the GitHub MCP path works.",
        )
    )
    print(result)