"""Product response models."""

from datetime import datetime

from pydantic import Field

from yazio_mcp.models.base import YazioResponseModel


class ProductServing(YazioResponseModel):
    """A serving conversion returned with a product."""

    serving: str | None = None
    amount: float | None = None


class Product(YazioResponseModel):
    """Known product details; nutrient values are per one base unit."""

    name: str | None = None
    producer: str | None = None
    category: str | None = None
    base_unit: str | None = None
    is_verified: bool | None = None
    is_private: bool | None = None
    is_deleted: bool | None = None
    has_ean: bool | None = None
    nutrients: dict[str, float] = Field(default_factory=dict)
    servings: list[ProductServing] = Field(default_factory=list)
    eans: list[str] = Field(default_factory=list)
    language: str | None = None
    countries: list[str] = Field(default_factory=list)
    updated_at: datetime | None = None


class ProductSearchResult(YazioResponseModel):
    """One result returned by product search."""

    score: float | None = None
    name: str | None = None
    product_id: str | None = None
    serving: str | None = None
    serving_quantity: float | None = None
    amount: float | None = None
    base_unit: str | None = None
    producer: str | None = None
    is_verified: bool | None = None
    nutrients: dict[str, float] = Field(default_factory=dict)
    countries: list[str] = Field(default_factory=list)
    language: str | None = None
