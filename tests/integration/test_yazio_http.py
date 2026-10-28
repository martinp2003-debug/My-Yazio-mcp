import asyncio
import json
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
import respx
from pydantic import SecretStr

from yazio_mcp.adapters.yazio_http import YazioHttpClient
from yazio_mcp.config import Settings
from yazio_mcp.errors import (
    YazioAuthenticationError,
    YazioHttpError,
    YazioInvalidResponseError,
    YazioTransportError,
    YazioVersionBlockedError,
)

API_BASE_URL = "https://example.invalid/v22"
TOKEN_URL = f"{API_BASE_URL}/oauth/token"
USER_AGENT = "YAZIO/test sanitized"


class MutableClock:
    def __init__(self, value: float = 100.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value


def make_settings() -> Settings:
    return Settings(
        username=SecretStr("person@example.invalid"),
        password=SecretStr("sanitized-password"),
        api_base_url=API_BASE_URL,
        user_agent=USER_AGENT,
        connect_timeout_seconds=1,
        read_timeout_seconds=2,
    )


def token_response(
    access_token: str,
    *,
    expires_in: float = 60,
    refresh_token: str | None = None,
) -> httpx.Response:
    payload: dict[str, Any] = {
        "access_token": access_token,
        "expires_in": expires_in,
        "token_type": "bearer",
    }
    if refresh_token is not None:
        payload["refresh_token"] = refresh_token
    return httpx.Response(200, json=payload)


def request_json(request: httpx.Request) -> dict[str, str]:
    value: dict[str, str] = json.loads(request.content)
    return value


@pytest.fixture
def mocked_yazio() -> Iterator[respx.MockRouter]:
    with respx.mock(assert_all_called=True) as router:
        yield router


async def test_password_authentication_uses_relative_v22_path_and_shared_token(
    mocked_yazio: respx.MockRouter,
) -> None:
    route = mocked_yazio.post(TOKEN_URL).mock(
        return_value=token_response("access-one", refresh_token="refresh-one")
    )
    client = YazioHttpClient(make_settings())

    first, second = await asyncio.gather(
        client.get_access_token(),
        client.get_access_token(),
    )

    assert first == second == "access-one"
    assert route.call_count == 1
    request = route.calls[0].request
    assert str(request.url) == TOKEN_URL
    assert request.headers["User-Agent"] == USER_AGENT
    assert request_json(request) == {
        "username": "person@example.invalid",
        "password": "sanitized-password",
        "grant_type": "password",
        "client_id": "3_5rbw4kehpugw8ogsc8ck8oo4ogswgckcskc04gcg8kk8k48ssw",
        "client_secret": "25gdtt1hvdi8gwowoww4oo88sgsw0oo04o0og0kkgwwks8k0k",
    }

    await client.aclose()
    assert client.is_closed


async def test_expired_token_is_refreshed_and_keeps_previous_refresh_token(
    mocked_yazio: respx.MockRouter,
) -> None:
    clock = MutableClock()
    route = mocked_yazio.post(TOKEN_URL).mock(
        side_effect=[
            token_response("access-one", expires_in=10, refresh_token="refresh-one"),
            token_response("access-two", expires_in=10),
            token_response("access-three", expires_in=10),
        ]
    )

    async with YazioHttpClient(make_settings(), clock=clock) as client:
        assert await client.get_access_token() == "access-one"
        clock.value = 110
        assert await client.get_access_token() == "access-two"
        clock.value = 120
        assert await client.get_access_token() == "access-three"

    assert route.call_count == 3
    assert request_json(route.calls[1].request) == {
        "grant_type": "refresh_token",
        "refresh_token": "refresh-one",
        "client_id": "3_5rbw4kehpugw8ogsc8ck8oo4ogswgckcskc04gcg8kk8k48ssw",
        "client_secret": "25gdtt1hvdi8gwowoww4oo88sgsw0oo04o0og0kkgwwks8k0k",
    }
    assert request_json(route.calls[2].request)["refresh_token"] == "refresh-one"


async def test_expired_token_without_refresh_token_reauthenticates(
    mocked_yazio: respx.MockRouter,
) -> None:
    clock = MutableClock()
    route = mocked_yazio.post(TOKEN_URL).mock(
        side_effect=[
            token_response("access-one", expires_in=5),
            token_response("access-two", expires_in=5),
        ]
    )

    async with YazioHttpClient(make_settings(), clock=clock) as client:
        assert await client.get_access_token() == "access-one"
        clock.value = 105
        assert await client.get_access_token() == "access-two"

    assert route.call_count == 2
    assert request_json(route.calls[1].request)["grant_type"] == "password"


async def test_rejected_refresh_token_falls_back_to_password(
    mocked_yazio: respx.MockRouter,
) -> None:
    clock = MutableClock()
    route = mocked_yazio.post(TOKEN_URL).mock(
        side_effect=[
            token_response("access-one", expires_in=5, refresh_token="refresh-one"),
            httpx.Response(401, json={"error": "invalid_grant"}),
            token_response("access-two", expires_in=5),
        ]
    )

    async with YazioHttpClient(make_settings(), clock=clock) as client:
        assert await client.get_access_token() == "access-one"
        clock.value = 105
        assert await client.get_access_token() == "access-two"

    assert route.call_count == 3
    assert request_json(route.calls[1].request)["grant_type"] == "refresh_token"
    assert request_json(route.calls[2].request)["grant_type"] == "password"


@pytest.mark.parametrize(
    ("response", "error_type", "code"),
    [
        (
            httpx.Response(403, json={"error": "version_blocked"}),
            YazioVersionBlockedError,
            "version_blocked",
        ),
        (
            httpx.Response(401, json={"error": "invalid_grant"}),
            YazioAuthenticationError,
            "authentication_failed",
        ),
        (
            httpx.Response(500, text="upstream failure"),
            YazioHttpError,
            "http_error",
        ),
        (
            httpx.Response(200, text="not json"),
            YazioInvalidResponseError,
            "invalid_response",
        ),
    ],
)
async def test_http_and_response_errors_are_stable_and_sanitized(
    mocked_yazio: respx.MockRouter,
    response: httpx.Response,
    error_type: type[Exception],
    code: str,
) -> None:
    mocked_yazio.post(TOKEN_URL).mock(return_value=response)

    async with YazioHttpClient(make_settings()) as client:
        with pytest.raises(error_type) as captured:
            await client.get_access_token()

    error = captured.value
    assert getattr(error, "code") == code
    rendered = str(error) + repr(error)
    assert "person@example.invalid" not in rendered
    assert "sanitized-password" not in rendered


async def test_transport_errors_are_translated_without_request_details(
    mocked_yazio: respx.MockRouter,
) -> None:
    mocked_yazio.post(TOKEN_URL).mock(
        side_effect=httpx.ConnectTimeout("sanitized transport failure")
    )

    async with YazioHttpClient(make_settings()) as client:
        with pytest.raises(YazioTransportError) as captured:
            await client.get_access_token()

    assert captured.value.code == "transport_error"
    assert TOKEN_URL not in str(captured.value)
