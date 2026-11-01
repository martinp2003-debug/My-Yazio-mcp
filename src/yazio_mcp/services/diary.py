"""Diary use cases independent from HTTP and FastMCP."""

from collections.abc import Callable
from datetime import date
from uuid import UUID, uuid4

from yazio_mcp.errors import (
    YazioItemNotFoundError,
    YazioMutationVerificationError,
)
from yazio_mcp.models import (
    ConsumedItemBucket,
    ConsumedItems,
    ConsumedProductWrite,
    DailySummary,
    DiaryMutationResult,
)
from yazio_mcp.ports import YazioGateway


class DiaryService:
    """Coordinate diary reads through the gateway port."""

    def __init__(
        self,
        gateway: YazioGateway,
        *,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._gateway = gateway
        self._id_factory = id_factory

    async def get_daily_summary(self, day: date) -> DailySummary:
        """Return the summary for the requested local calendar day."""
        return await self._gateway.get_user_daily_summary(day)

    async def get_consumed_items(self, day: date) -> ConsumedItems:
        """Return all consumed-item buckets for the requested day."""
        return await self._gateway.get_user_consumed_items(day)

    async def add_consumed_product(
        self,
        *,
        product_id: str,
        amount: float,
        daytime: str,
        consumed_at: str,
        serving: str | None = None,
        serving_quantity: float | None = None,
    ) -> DiaryMutationResult:
        """Add one product and confirm its generated id through a diary read."""
        item = ConsumedProductWrite(
            id=str(self._id_factory()),
            product_id=product_id,
            amount=amount,
            daytime=daytime,
            consumed_at=consumed_at,
            serving=serving,
            serving_quantity=serving_quantity,
        )
        await self._gateway.add_consumed_product(item)
        items = await self._gateway.get_user_consumed_items(item.day)
        if not self._contains(items, "products", item.id):
            raise YazioMutationVerificationError()
        return DiaryMutationResult(entry_id=item.id, bucket="products")

    async def delete_consumed_item(
        self,
        *,
        day: date,
        bucket: ConsumedItemBucket,
        entry_id: str,
    ) -> DiaryMutationResult:
        """Delete an existing item and confirm that its id disappeared."""
        before = await self._gateway.get_user_consumed_items(day)
        if not self._contains(before, bucket, entry_id):
            raise YazioItemNotFoundError()

        await self._gateway.delete_consumed_item(bucket, entry_id)
        after = await self._gateway.get_user_consumed_items(day)
        if self._contains(after, bucket, entry_id):
            raise YazioMutationVerificationError()
        return DiaryMutationResult(entry_id=entry_id, bucket=bucket)

    @staticmethod
    def _contains(
        items: ConsumedItems,
        bucket: ConsumedItemBucket,
        entry_id: str,
    ) -> bool:
        return any(
            getattr(item, "id", None) == entry_id
            for item in getattr(items, bucket)
        )
