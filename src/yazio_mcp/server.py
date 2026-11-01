"""FastMCP application and HTTP entry point."""

import argparse
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field
from starlette.requests import Request
from starlette.responses import JSONResponse

from yazio_mcp.adapters import YazioHttpClient
from yazio_mcp.config import Settings
from yazio_mcp.models import (
    ConsumedItemBucket,
    ConsumedItems,
    DailySummary,
    DiaryMutationResult,
    Product,
    ProductSearchResult,
    UserProfile,
)
from yazio_mcp.ports import YazioGateway
from yazio_mcp.services import DiaryService

MCP_HOST = "127.0.0.1"
MCP_PORT = 8000
MCP_PATH = "/mcp"

_gateway: YazioGateway | None = None


def get_health() -> dict[str, str]:
    """Return local process health without contacting YAZIO."""
    return {"status": "ok", "service": "yazio-mcp"}


def _get_gateway() -> YazioGateway:
    """Create the shared adapter only when a YAZIO tool is first called."""
    global _gateway
    if _gateway is None:
        # Required fields are supplied by pydantic-settings environment sources.
        _gateway = YazioHttpClient(Settings())  # type: ignore[call-arg]
    return _gateway


@asynccontextmanager
async def _lifespan(_server: FastMCP[Any]) -> AsyncGenerator[dict[str, object], None]:
    """Close a lazily created HTTP pool when FastMCP shuts down."""
    global _gateway
    try:
        yield {}
    finally:
        if isinstance(_gateway, YazioHttpClient):
            await _gateway.aclose()
            _gateway = None


mcp = FastMCP("YAZIO MCP", lifespan=_lifespan)


@mcp.tool
async def health_check() -> dict[str, str]:
    """Check that the MCP server is running; this does not contact YAZIO."""
    return get_health()


@mcp.tool
async def get_user() -> UserProfile:
    """Get the authenticated YAZIO profile from the observed private v22 API."""
    return await _get_gateway().get_user()


@mcp.tool
async def get_user_daily_summary(day: date) -> DailySummary:
    """Get the observed nutrition summary for one local calendar day."""
    return await DiaryService(_get_gateway()).get_daily_summary(day)


@mcp.tool
async def get_user_consumed_items(day: date) -> ConsumedItems:
    """Get products, simple products and recipe portions logged for one day."""
    return await DiaryService(_get_gateway()).get_consumed_items(day)


@mcp.tool
async def search_products(
    query: str,
    sex: str,
    countries: str,
    locales: str | None = None,
) -> list[ProductSearchResult]:
    """Search observed YAZIO products; sex and countries are required upstream."""
    return await _get_gateway().search_products(
        query,
        sex=sex,
        countries=countries,
        locales=locales,
    )


@mcp.tool
async def get_product(product_id: str) -> Product:
    """Get observed details and per-base-unit nutrients for one YAZIO product."""
    return await _get_gateway().get_product(product_id)


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    }
)
async def add_consumed_product(
    product_id: Annotated[str, Field(min_length=1)],
    amount: Annotated[float, Field(gt=0)],
    daytime: Annotated[str, Field(min_length=1)],
    consumed_at: Annotated[
        str,
        Field(
            pattern=r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}$",
            description="Local time as YYYY-MM-DDTHH:MM:SS; no timezone offset.",
        ),
    ],
    serving: str | None = None,
    serving_quantity: Annotated[float, Field(gt=0)] | None = None,
) -> DiaryMutationResult:
    """Add one YAZIO product and return only after read-back verification."""
    return await DiaryService(_get_gateway()).add_consumed_product(
        product_id=product_id,
        amount=amount,
        daytime=daytime,
        consumed_at=consumed_at,
        serving=serving,
        serving_quantity=serving_quantity,
    )


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": True,
    }
)
async def delete_consumed_item(
    day: date,
    bucket: ConsumedItemBucket,
    entry_id: Annotated[str, Field(min_length=1)],
) -> DiaryMutationResult:
    """Delete one known diary entry and verify its absence for the given day."""
    return await DiaryService(_get_gateway()).delete_consumed_item(
        day=day,
        bucket=bucket,
        entry_id=entry_id,
    )


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
