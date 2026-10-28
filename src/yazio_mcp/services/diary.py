"""Read-only diary use cases independent from HTTP and FastMCP."""

from datetime import date

from yazio_mcp.models import ConsumedItems, DailySummary
from yazio_mcp.ports import YazioGateway


class DiaryService:
    """Coordinate diary reads through the gateway port."""

    def __init__(self, gateway: YazioGateway) -> None:
        self._gateway = gateway

    async def get_daily_summary(self, day: date) -> DailySummary:
        """Return the summary for the requested local calendar day."""
        return await self._gateway.get_user_daily_summary(day)

    async def get_consumed_items(self, day: date) -> ConsumedItems:
        """Return all consumed-item buckets for the requested day."""
        return await self._gateway.get_user_consumed_items(day)
