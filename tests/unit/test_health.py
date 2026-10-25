from fastmcp import Client
from httpx import ASGITransport, AsyncClient

from yazio_mcp.server import app, mcp


async def test_health_check_tool() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("health_check")

    assert result.data == {"status": "ok", "service": "yazio-mcp"}


async def test_http_health_route() -> None:
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "yazio-mcp"}
