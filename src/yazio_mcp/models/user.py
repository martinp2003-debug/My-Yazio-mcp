"""User response models."""

from datetime import date

from pydantic import Field, SecretStr

from yazio_mcp.models.base import YazioResponseModel


class UserDiet(YazioResponseModel):
    """Diet distribution embedded in a user profile."""

    name: str | None = None
    carb_percentage: float | None = None
    fat_percentage: float | None = None
    protein_percentage: float | None = None


class UserProfile(YazioResponseModel):
    """Known fields from the observed user profile response."""

    first_name: str | None = Field(default=None, repr=False)
    last_name: object | None = Field(default=None, repr=False)
    sex: str | None = Field(default=None, repr=False)
    city: object | None = Field(default=None, repr=False)
    country: str | None = None
    language: str | None = None
    timezone_offset: float | None = None
    food_database_country: str | None = None
    goal: str | None = Field(default=None, repr=False)
    activity_degree: str | None = Field(default=None, repr=False)
    weight_change_per_week: float | None = Field(default=None, repr=False)
    unit_length: str | None = None
    unit_mass: str | None = None
    unit_energy: str | None = None
    unit_glucose: str | None = None
    unit_serving: str | None = None
    stripe_customer_id: SecretStr | None = None
    diet: UserDiet | None = Field(default=None, repr=False)
    registration_date: str | None = None
    reset_date: str | None = None
    profile_image: object | None = Field(default=None, repr=False)
    user_token: SecretStr | None = None
    email_confirmation_status: str | None = None
    newsletter_opt_in: bool | None = None
    login_type: str | None = None
    siwa_user_id: SecretStr | None = None
    premium_type: str | None = None
    start_weight: float | None = Field(default=None, repr=False)
    uuid: str | None = Field(default=None, repr=False)
    body_height: float | None = Field(default=None, repr=False)
    date_of_birth: date | None = Field(default=None, repr=False)
    email: SecretStr | None = None
    tags: list[object] = Field(default_factory=list)
