from pathlib import Path

from pydantic import ValidationError
from pytest import MonkeyPatch

from yazio_mcp.config import (
    DEFAULT_API_BASE_URL,
    DEFAULT_CONNECT_TIMEOUT_SECONDS,
    DEFAULT_READ_TIMEOUT_SECONDS,
    Settings,
)

YAZIO_ENVIRONMENT_VARIABLES = (
    "YAZIO_USERNAME",
    "YAZIO_PASSWORD",
    "YAZIO_API_BASE_URL",
    "YAZIO_USER_AGENT",
    "YAZIO_CONNECT_TIMEOUT_SECONDS",
    "YAZIO_READ_TIMEOUT_SECONDS",
)


def load_settings() -> Settings:
    """Exercise environment loading despite mypy seeing model fields as kwargs."""
    return Settings()  # type: ignore[call-arg]


def clear_yazio_environment(monkeypatch: MonkeyPatch) -> None:
    for variable in YAZIO_ENVIRONMENT_VARIABLES:
        monkeypatch.delenv(variable, raising=False)


def test_settings_load_environment_and_defaults(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    clear_yazio_environment(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("YAZIO_USERNAME", "person@example.invalid")
    monkeypatch.setenv("YAZIO_PASSWORD", "correct horse battery staple")
    monkeypatch.setenv("YAZIO_USER_AGENT", "YAZIO/test sanitized")

    settings = load_settings()

    assert settings.username.get_secret_value() == "person@example.invalid"
    assert settings.password.get_secret_value() == "correct horse battery staple"
    assert settings.api_base_url == DEFAULT_API_BASE_URL
    assert settings.connect_timeout_seconds == DEFAULT_CONNECT_TIMEOUT_SECONDS
    assert settings.read_timeout_seconds == DEFAULT_READ_TIMEOUT_SECONDS


def test_settings_load_all_configured_names(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    clear_yazio_environment(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("YAZIO_USERNAME", "person@example.invalid")
    monkeypatch.setenv("YAZIO_PASSWORD", "secret-password")
    monkeypatch.setenv("YAZIO_API_BASE_URL", "http://localhost:8080/v22/")
    monkeypatch.setenv("YAZIO_USER_AGENT", "YAZIO/test sanitized")
    monkeypatch.setenv("YAZIO_CONNECT_TIMEOUT_SECONDS", "1.5")
    monkeypatch.setenv("YAZIO_READ_TIMEOUT_SECONDS", "12")

    settings = load_settings()

    assert settings.api_base_url == "http://localhost:8080/v22"
    assert settings.user_agent == "YAZIO/test sanitized"
    assert settings.connect_timeout_seconds == 1.5
    assert settings.read_timeout_seconds == 12.0


def test_secrets_are_absent_from_repr_dump_and_validation_errors(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    clear_yazio_environment(monkeypatch)
    monkeypatch.chdir(tmp_path)
    username = "private-person@example.invalid"
    password = "private-password-value"
    monkeypatch.setenv("YAZIO_USERNAME", username)
    monkeypatch.setenv("YAZIO_PASSWORD", password)
    monkeypatch.setenv("YAZIO_USER_AGENT", "YAZIO/test sanitized")
    settings = load_settings()

    rendered = repr(settings) + settings.model_dump_json()

    assert username not in rendered
    assert password not in rendered

    monkeypatch.setenv("YAZIO_READ_TIMEOUT_SECONDS", password)
    try:
        load_settings()
    except ValidationError as error:
        assert password not in str(error)
    else:
        raise AssertionError("invalid timeout should fail validation")


def test_settings_reject_invalid_url_blank_user_agent_and_timeouts(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    clear_yazio_environment(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("YAZIO_USERNAME", "person@example.invalid")
    monkeypatch.setenv("YAZIO_PASSWORD", "secret-password")
    monkeypatch.setenv("YAZIO_API_BASE_URL", "not-a-url")
    monkeypatch.setenv("YAZIO_USER_AGENT", "   ")
    monkeypatch.setenv("YAZIO_CONNECT_TIMEOUT_SECONDS", "0")

    try:
        load_settings()
    except ValidationError as error:
        fields = {item["loc"][0] for item in error.errors()}
        assert fields == {"api_base_url", "user_agent", "connect_timeout_seconds"}
    else:
        raise AssertionError("invalid settings should fail validation")
