from datetime import date
from uuid import UUID

import pytest

from yazio_mcp.errors import YazioItemNotFoundError, YazioMutationVerificationError
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
from yazio_mcp.services import DiaryService


class FakeYazioGateway:
    def __init__(self) -> None:
        self.requested_summary_day: date | None = None
        self.requested_items_day: date | None = None
        self.items = ConsumedItems()
        self.added_item: ConsumedProductWrite | None = None
        self.deleted_item: tuple[ConsumedItemBucket, str] | None = None
        self.keep_deleted_item = False

    async def get_user(self) -> UserProfile:
        raise NotImplementedError

    async def get_user_daily_summary(self, day: date) -> DailySummary:
        self.requested_summary_day = day
        return DailySummary(steps=1234)

    async def get_user_consumed_items(self, day: date) -> ConsumedItems:
        self.requested_items_day = day
        return self.items

    async def search_products(
        self,
        query: str,
        *,
        sex: str,
        countries: str,
        locales: str | None = None,
    ) -> list[ProductSearchResult]:
        raise NotImplementedError

    async def get_product(self, product_id: str) -> Product:
        raise NotImplementedError

    async def add_consumed_product(self, item: ConsumedProductWrite) -> None:
        self.added_item = item
        self.items.products.append(ConsumedProduct(id=item.id))

    async def delete_consumed_item(
        self,
        bucket: ConsumedItemBucket,
        entry_id: str,
    ) -> None:
        self.deleted_item = (bucket, entry_id)
        if not self.keep_deleted_item:
            entries = getattr(self.items, bucket)
            entries[:] = [
                item for item in entries if getattr(item, "id", None) != entry_id
            ]


class DiscardingWriteGateway(FakeYazioGateway):
    async def add_consumed_product(self, item: ConsumedProductWrite) -> None:
        self.added_item = item


async def test_diary_service_uses_fake_gateway_without_http() -> None:
    gateway = FakeYazioGateway()
    service = DiaryService(gateway)
    requested_day = date(2026, 10, 27)

    summary = await service.get_daily_summary(requested_day)
    items = await service.get_consumed_items(requested_day)

    assert summary.steps == 1234
    assert items == ConsumedItems()
    assert gateway.requested_summary_day == requested_day
    assert gateway.requested_items_day == requested_day


async def test_add_product_generates_id_and_verifies_read_back() -> None:
    gateway = FakeYazioGateway()
    entry_uuid = UUID("00000000-0000-0000-0000-000000000010")
    service = DiaryService(gateway, id_factory=lambda: entry_uuid)

    result = await service.add_consumed_product(
        product_id="product-id",
        amount=125,
        daytime="lunch",
        consumed_at="2026-10-31T12:30:00",
        serving="gram",
        serving_quantity=1,
    )

    assert gateway.added_item is not None
    assert gateway.added_item.id == str(entry_uuid)
    assert gateway.added_item.consumed_at == "2026-10-31 12:30:00"
    assert gateway.requested_items_day == date(2026, 10, 31)
    assert result.model_dump() == {
        "entry_id": str(entry_uuid),
        "bucket": "products",
        "verified": True,
    }


async def test_add_product_fails_when_read_back_does_not_contain_id() -> None:
    gateway = DiscardingWriteGateway()
    service = DiaryService(gateway)

    with pytest.raises(YazioMutationVerificationError):
        await service.add_consumed_product(
            product_id="product-id",
            amount=1,
            daytime="snack",
            consumed_at="2026-10-31T15:00:00",
        )


async def test_delete_requires_existing_item_and_verifies_absence() -> None:
    gateway = FakeYazioGateway()
    gateway.items.products.append(ConsumedProduct(id="entry-id"))
    service = DiaryService(gateway)

    result = await service.delete_consumed_item(
        day=date(2026, 10, 31),
        bucket="products",
        entry_id="entry-id",
    )

    assert gateway.deleted_item == ("products", "entry-id")
    assert result.verified is True

    with pytest.raises(YazioItemNotFoundError):
        await service.delete_consumed_item(
            day=date(2026, 10, 31),
            bucket="products",
            entry_id="missing-id",
        )


async def test_delete_fails_when_item_remains_after_acknowledgement() -> None:
    gateway = FakeYazioGateway()
    gateway.items.products.append(ConsumedProduct(id="entry-id"))
    gateway.keep_deleted_item = True

    with pytest.raises(YazioMutationVerificationError):
        await DiaryService(gateway).delete_consumed_item(
            day=date(2026, 10, 31),
            bucket="products",
            entry_id="entry-id",
        )
