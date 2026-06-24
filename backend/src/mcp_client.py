from contextlib import asynccontextmanager

from fastmcp import Client

from .config import settings


@asynccontextmanager
async def planner_client():
    """Open a session against the Planner MCP server.

    Uses fastmcp's built-in OAuth flow ("auth='oauth'"): the first call opens
    a browser for Microsoft sign-in, then caches the token locally so later
    calls reuse it silently. Only works for a server process running on a
    machine with a browser available to the signed-in user (fine for this
    single-user, local-only app).
    """
    async with Client(settings.planner_mcp_url, auth="oauth") as client:
        yield client


async def call_tool(name: str, arguments: dict | None = None):
    async with planner_client() as client:
        result = await client.call_tool(name, arguments or {})
        return result.data
