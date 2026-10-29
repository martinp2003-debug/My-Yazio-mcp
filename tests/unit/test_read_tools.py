from datetime import date

import pytest
from fastmcp import Client

import yazio_mcp.server as server
from yazio_mcp.models import (
    ConsumedItems,
    ConsumedProduct,
    DailySummary,
    Product,
    ProductSearchResult,
    UserProfile,
)


class FakeYazioGateway:
    async def get_user(self) -> UserProfile:
        return UserProfile(country="FR")

    async def get_user_daily_summary(self, day: date) -> DailySummary:
        return DailySummary.model_validate(
            {"steps": 1234, "requested_day": day.isoformat()}
        )

    async def get_user_consumed_items(self, day: date) -> ConsumedItems:
        return ConsumedItems.model_validate(
            {
                "products": [ConsumedProduct(id="entry-id")],
                "requested_day": day.isoformat(),
            }
        )

    async def search_products(
        self,
        query: str,
        *,
        sex: str,
        countries: str,
        locales: str | None = None,
    ) -> list[ProductSearchResult]:
        return [
            ProductSearchResult.model_validate(
                {
                    "product_id": "product-id",
                    "received": [query, sex, countries, locales],
                }
            )
        ]

    async def get_product(self, product_id: str) -> Product:
        return Product.model_validate(
            {"name": "Sanitized product", "requested_id": product_id}
        )


async def test_read_tools_are_thin_gateway_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(server, "_gateway", FakeYazioGateway())

    async with Client(server.mcp) as client:
        user = await client.call_tool("get_user")
        summary = await client.call_tool(
            "get_user_daily_summary", {"day": "2026-10-27"}
        )
        items = await client.call_tool(
            "get_user_consumed_items", {"day": "2026-10-27"}
        )
        search = await client.call_tool(
            "search_products",
            {
                "query": "banana",
                "sex": "not_specified",
                "countries": "FR",
                "locales": "fr-FR",
            },
        )
        product = await client.call_tool(
            "get_product", {"product_id": "product-id"}
        )

    user_data = user.data.model_dump()
    summary_data = summary.data.model_dump()
    items_data = items.data.model_dump()
    search_data = [item.model_dump() for item in search.data]
    product_data = product.data.model_dump()

    assert user_data["country"] == "FR"
    assert summary_data["steps"] == 1234
    assert summary_data["requested_day"] == "2026-10-27"
    assert items_data["products"][0]["id"] == "entry-id"
    assert search_data[0]["received"] == [
        "banana",
        "not_specified",
        "FR",
        "fr-FR",
    ]
    assert product_data["requested_id"] == "product-id"
