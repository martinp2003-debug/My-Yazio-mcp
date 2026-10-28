"""Port used by services to read data from YAZIO."""

from datetime import date
from typing import Protocol

from yazio_mcp.models import (
    ConsumedItems,
    DailySummary,
    Product,
    ProductSearchResult,
    UserProfile,
)


class YazioGateway(Protocol):
    """Asynchronous operations whose observed payloads are already modelled."""

    async def get_user(self) -> UserProfile:
        """Return the authenticated user's profile."""
        ...

    async def get_user_daily_summary(self, day: date) -> DailySummary:
        """Return the daily summary for one local calendar day."""
        ...

    async def get_user_consumed_items(self, day: date) -> ConsumedItems:
        """Return all consumed-item buckets for one local calendar day."""
        ...

    async def search_products(
        self,
        query: str,
        *,
        sex: str,
        countries: str,
        locales: str | None = None,
    ) -> list[ProductSearchResult]:
        """Search products using the parameters observed as required by YAZIO."""
        ...

    async def get_product(self, product_id: str) -> Product:
        """Return one product by its YAZIO identifier."""
        ...
