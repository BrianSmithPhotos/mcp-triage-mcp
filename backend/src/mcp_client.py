import asyncio

from fastmcp import Client

from .config import settings

# A single long-lived connection, reused for the life of the backend process.
# Authenticates once via fastmcp's built-in OAuth flow ("auth='oauth'"): the first
# call opens a browser for Microsoft sign-in, then the resulting token is reused
# for every subsequent tool call until the backend restarts. Opening a fresh
# Client per request would mean a fresh OAuth handshake per request, since
# fastmcp's default token storage is in-memory and scoped to the Client instance.
_client = Client(settings.planner_mcp_url, auth="oauth")
_connect_lock = asyncio.Lock()
_connected = False


async def get_client() -> Client:
    global _connected
    async with _connect_lock:
        if not _connected:
            await _client.__aenter__()
            _connected = True
    return _client


async def disconnect() -> None:
    global _connected
    if _connected:
        await _client.__aexit__(None, None, None)
        _connected = False
