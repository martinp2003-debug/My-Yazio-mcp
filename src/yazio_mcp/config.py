"""Environment-backed configuration for the private YAZIO API."""

from typing import Any

from pydantic import AnyHttpUrl, Field, SecretStr, TypeAdapter, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_API_BASE_URL = "https://yzapi.yazio.com/v22"
DEFAULT_CONNECT_TIMEOUT_SECONDS = 5.0
DEFAULT_READ_TIMEOUT_SECONDS = 30.0


class Settings(BaseSettings):
    """Load YAZIO settings without exposing credentials in representations."""

    model_config = SettingsConfigDict(
        env_prefix="YAZIO_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    username: SecretStr = Field(min_length=1)
    password: SecretStr = Field(min_length=1)
    api_base_url: str = DEFAULT_API_BASE_URL
    user_agent: str = Field(min_length=1)
    connect_timeout_seconds: float = Field(
        default=DEFAULT_CONNECT_TIMEOUT_SECONDS,
        gt=0,
    )
    read_timeout_seconds: float = Field(
        default=DEFAULT_READ_TIMEOUT_SECONDS,
        gt=0,
    )

    @field_validator("api_base_url")
    @classmethod
    def validate_api_base_url(cls, value: str) -> str:
        """Validate the HTTP URL and store it without a trailing slash."""
        url = TypeAdapter(AnyHttpUrl).validate_python(value)
        if url.query is not None or url.fragment is not None:
            raise ValueError("api_base_url must not contain a query or fragment")
        return str(url).rstrip("/")

    @field_validator("user_agent")
    @classmethod
    def reject_blank_user_agent(cls, value: str) -> str:
        """Reject whitespace-only values while preserving the configured value."""
        if not value.strip():
            raise ValueError("user_agent must not be blank")
        return value

    def __repr_args__(self) -> list[tuple[str | None, Any]]:
        """Keep both account credentials out of the settings representation."""
        return [
            (name, value)
            for name, value in super().__repr_args__()
            if name not in {"username", "password"}
        ]
