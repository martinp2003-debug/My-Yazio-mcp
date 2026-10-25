"""FastMCP application and HTTP entry point."""

import argparse

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

MCP_HOST = "127.0.0.1"
MCP_PORT = 8000
MCP_PATH = "/mcp"


def get_health() -> dict[str, str]:
    """Return local process health without contacting YAZIO."""
    return {"status": "ok", "service": "yazio-mcp"}


mcp = FastMCP("YAZIO MCP")


@mcp.tool
async def health_check() -> dict[str, str]:
    """Check that the MCP server is running; this does not contact YAZIO."""
    return get_health()


@mcp.custom_route("/health", methods=["GET"])
async def health_route(_request: Request) -> JSONResponse:
    """Expose a conventional HTTP health endpoint for deployment probes."""
    return JSONResponse(get_health())


app = mcp.http_app(path=MCP_PATH)


def main() -> None:
    """Run the MCP server over Streamable HTTP."""
    parser = argparse.ArgumentParser(description="Run the YAZIO MCP server")
    parser.add_argument("--host", default=MCP_HOST)
    parser.add_argument("--port", default=MCP_PORT, type=int)
    parser.add_argument("--path", default=MCP_PATH)
    args = parser.parse_args()

    mcp.run(transport="http", host=args.host, port=args.port, path=args.path)


if __name__ == "__main__":
    main()
