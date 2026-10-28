from datetime import date

from yazio_mcp.models import (
    ConsumedItems,
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

    async def get_user(self) -> UserProfile:
        raise NotImplementedError

    async def get_user_daily_summary(self, day: date) -> DailySummary:
        self.requested_summary_day = day
        return DailySummary(steps=1234)

    async def get_user_consumed_items(self, day: date) -> ConsumedItems:
        self.requested_items_day = day
        return ConsumedItems()

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
