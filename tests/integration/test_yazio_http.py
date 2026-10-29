import asyncio
import json
from collections.abc import Iterator
from datetime import date
from pathlib import Path
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
FIXTURES = Path(__file__).parents[1] / "fixtures"


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


def load_fixture(name: str) -> Any:
    with (FIXTURES / name).open(encoding="utf-8") as fixture:
        return json.load(fixture)


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
            httpx.Response(400, json={"error": "invalid_grant"}),
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


async def test_all_read_methods_use_observed_v22_routes_and_bearer_auth(
    mocked_yazio: respx.MockRouter,
) -> None:
    mocked_yazio.post(TOKEN_URL).mock(return_value=token_response("access-one"))
    user_route = mocked_yazio.get(f"{API_BASE_URL}/user").mock(
        return_value=httpx.Response(200, json=load_fixture("user_profile.json"))
    )
    summary_route = mocked_yazio.get(
        f"{API_BASE_URL}/user/widgets/daily-summary"
    ).mock(return_value=httpx.Response(200, json=load_fixture("daily_summary.json")))
    items_route = mocked_yazio.get(f"{API_BASE_URL}/user/consumed-items").mock(
        return_value=httpx.Response(200, json=load_fixture("consumed_items.json"))
    )
    search_route = mocked_yazio.get(f"{API_BASE_URL}/products/search").mock(
        return_value=httpx.Response(
            200,
            json=[load_fixture("product_search_result.json")],
        )
    )
    product_id = "00000000-0000-0000-0000-000000000006"
    product_route = mocked_yazio.get(
        f"{API_BASE_URL}/products/{product_id}"
    ).mock(return_value=httpx.Response(200, json=load_fixture("product.json")))

    async with YazioHttpClient(make_settings()) as client:
        user = await client.get_user()
        summary = await client.get_user_daily_summary(date(2026, 10, 27))
        items = await client.get_user_consumed_items(date(2026, 10, 27))
        results = await client.search_products(
            "sanitized query",
            sex="not_specified",
            countries="FR",
            locales="fr-FR",
        )
        product = await client.get_product(product_id)

    assert user.country == "FR"
    assert summary.steps == 8000
    assert len(items.products) == 1
    assert results[0].product_id == product_id
    assert product.name == "Sanitized product"
    assert dict(summary_route.calls[0].request.url.params) == {
        "date": "2026-10-27"
    }
    assert dict(items_route.calls[0].request.url.params) == {"date": "2026-10-27"}
    assert dict(search_route.calls[0].request.url.params) == {
        "query": "sanitized query",
        "sex": "not_specified",
        "countries": "FR",
        "locales": "fr-FR",
    }
    assert search_route.calls[0].request.headers["Accept-Language"] == "fr-FR"
    for route in (user_route, summary_route, items_route, search_route, product_route):
        assert route.calls[0].request.headers["Authorization"] == "Bearer access-one"


async def test_partial_read_response_is_accepted(
    mocked_yazio: respx.MockRouter,
) -> None:
    mocked_yazio.post(TOKEN_URL).mock(return_value=token_response("access-one"))
    mocked_yazio.get(f"{API_BASE_URL}/user/consumed-items").mock(
        return_value=httpx.Response(200, json={})
    )

    async with YazioHttpClient(make_settings()) as client:
        items = await client.get_user_consumed_items(date(2026, 10, 27))

    assert items.products == []
    assert items.simple_products == []
    assert items.recipe_portions == []


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, json=[]),
        httpx.Response(200, text="not json"),
    ],
)
async def test_invalid_read_response_is_translated(
    mocked_yazio: respx.MockRouter,
    response: httpx.Response,
) -> None:
    mocked_yazio.post(TOKEN_URL).mock(return_value=token_response("access-one"))
    mocked_yazio.get(f"{API_BASE_URL}/products/product-id").mock(
        return_value=response
    )

    async with YazioHttpClient(make_settings()) as client:
        with pytest.raises(YazioInvalidResponseError):
            await client.get_product("product-id")


@pytest.mark.parametrize("status_code", [400, 500])
async def test_read_http_error_is_translated_without_response_body(
    mocked_yazio: respx.MockRouter,
    status_code: int,
) -> None:
    mocked_yazio.post(TOKEN_URL).mock(return_value=token_response("access-one"))
    mocked_yazio.get(f"{API_BASE_URL}/products/product-id").mock(
        return_value=httpx.Response(status_code, json={"private": "health-data"})
    )

    async with YazioHttpClient(make_settings()) as client:
        with pytest.raises(YazioHttpError) as captured:
            await client.get_product("product-id")

    assert "health-data" not in str(captured.value) + repr(captured.value)
