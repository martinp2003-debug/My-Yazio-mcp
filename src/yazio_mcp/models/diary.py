"""Food diary and daily summary response models."""

from datetime import datetime
from typing import Annotated

from pydantic import Field, WithJsonSchema

from yazio_mcp.models.base import YazioResponseModel

YazioLocalDateTime = Annotated[
    datetime,
    WithJsonSchema(
        {
            "type": "string",
            "description": (
                "Local timestamp observed from YAZIO; a timezone offset may be absent."
            ),
        },
        mode="serialization",
    ),
]


class ConsumedProduct(YazioResponseModel):
    """A product consumption returned by the diary endpoint."""

    id: str | None = None
    serving: str | None = None
    amount: float | None = None
    daytime: str | None = None
    date: YazioLocalDateTime | None = None
    type: str | None = None
    product_id: str | None = None
    serving_quantity: float | None = None


class SimpleProduct(YazioResponseModel):
    """A simple diary entry whose fields are not yet documented."""


class ConsumedRecipePortion(YazioResponseModel):
    """A consumed portion of a recipe."""

    id: str | None = None
    date: YazioLocalDateTime | None = None
    daytime: str | None = None
    type: str | None = None
    recipe_id: str | None = None
    portion_count: float | None = None


class ConsumedItems(YazioResponseModel):
    """The three independently typed diary buckets."""

    products: list[ConsumedProduct] = Field(default_factory=list)
    simple_products: list[SimpleProduct] = Field(default_factory=list)
    recipe_portions: list[ConsumedRecipePortion] = Field(default_factory=list)


class NutrientSummary(YazioResponseModel):
    """Energy and macro values keyed as observed by YAZIO."""

    energy: float | None = Field(default=None, alias="energy.energy")
    carbohydrate: float | None = Field(default=None, alias="nutrient.carb")
    fat: float | None = Field(default=None, alias="nutrient.fat")
    protein: float | None = Field(default=None, alias="nutrient.protein")


class DailyGoals(NutrientSummary):
    """Daily goals embedded in the summary widget."""

    water: float | None = None
    steps: float | None = Field(default=None, alias="activity.step")
    weight: float | None = Field(default=None, alias="bodyvalue.weight")


class MealSummary(YazioResponseModel):
    """Energy goal and consumed nutrients for one meal."""

    energy_goal: float | None = None
    nutrients: NutrientSummary | None = None


class DailySummaryUnits(YazioResponseModel):
    """Units reported by the daily summary."""

    unit_mass: str | None = None
    unit_energy: str | None = None
    unit_serving: str | None = None
    unit_length: str | None = None


class DailySummaryMeals(YazioResponseModel):
    """Known meal slots in a daily summary."""

    breakfast: MealSummary | None = None
    lunch: MealSummary | None = None
    dinner: MealSummary | None = None
    snack: MealSummary | None = None


class DailySummaryUser(YazioResponseModel):
    """User values embedded in a daily summary."""

    start_weight: float | None = Field(default=None, repr=False)
    current_weight: float | None = Field(default=None, repr=False)
    goal: str | None = Field(default=None, repr=False)
    sex: str | None = Field(default=None, repr=False)


class DailySummary(YazioResponseModel):
    """Daily summary widget response."""

    activity_energy: float | None = None
    consume_activity_energy: bool | None = None
    steps: float | None = None
    water_intake: float | None = None
    goals: DailyGoals | None = None
    units: DailySummaryUnits | None = None
    meals: DailySummaryMeals | None = None
    user: DailySummaryUser | None = Field(default=None, repr=False)
    active_fasting_countdown_template_key: dict[str, object] | None = None
