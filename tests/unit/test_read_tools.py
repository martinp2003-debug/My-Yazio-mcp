from datetime import date

import pytest
from fastmcp import Client

import yazio_mcp.server as server
from yazio_mcp.models import (
    ConsumedItemBucket,
    ConsumedItems,
    ConsumedProduct,
    ConsumedProductWrite,
    DailySummary,
    Product,
    ProductSearchResult,
    UserProfile,
)


class FakeYazioGateway:
    def __init__(self) -> None:
        self.items = ConsumedItems(products=[ConsumedProduct(id="entry-id")])

    async def get_user(self) -> UserProfile:
        return UserProfile(country="FR")

    async def get_user_daily_summary(self, day: date) -> DailySummary:
        return DailySummary.model_validate(
            {"steps": 1234, "requested_day": day.isoformat()}
        )

    async def get_user_consumed_items(self, day: date) -> ConsumedItems:
        return ConsumedItems.model_validate(
            {
                **self.items.model_dump(),
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

    async def add_consumed_product(self, item: ConsumedProductWrite) -> None:
        self.items.products.append(ConsumedProduct(id=item.id))

    async def delete_consumed_item(
        self,
        bucket: ConsumedItemBucket,
        entry_id: str,
    ) -> None:
        entries = getattr(self.items, bucket)
        entries[:] = [item for item in entries if getattr(item, "id", None) != entry_id]


async def test_read_tools_are_thin_gateway_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = FakeYazioGateway()
    monkeypatch.setattr(server, "_gateway", gateway)

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
        added = await client.call_tool(
            "add_consumed_product",
            {
                "product_id": "product-id",
                "amount": 125,
                "daytime": "lunch",
                "consumed_at": "2026-10-27T12:30:00",
                "serving": "gram",
                "serving_quantity": 1,
            },
        )
        deleted = await client.call_tool(
            "delete_consumed_item",
            {
                "day": "2026-10-27",
                "bucket": "products",
                "entry_id": added.data.entry_id,
            },
        )

    user_data = user.data.model_dump()
    summary_data = summary.data.model_dump()
    items_data = items.data.model_dump()
    search_data = [item.model_dump() for item in search.data]
    product_data = product.data.model_dump()
    added_data = added.structured_content
    deleted_data = deleted.structured_content

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
    assert added_data["verified"] is True
    assert added_data["bucket"] == "products"
    assert deleted_data == added_data
