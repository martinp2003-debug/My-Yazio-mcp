"""HTTP adapter and in-memory OAuth lifecycle for the private YAZIO API."""

import asyncio
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date
from types import TracebackType
from typing import Any, TypeVar
from urllib.parse import quote

import httpx
from pydantic import BaseModel, TypeAdapter, ValidationError

from yazio_mcp.config import Settings
from yazio_mcp.errors import (
    YazioAuthenticationError,
    YazioHttpError,
    YazioInvalidResponseError,
    YazioTransportError,
    YazioVersionBlockedError,
)
from yazio_mcp.models import (
    ConsumedItems,
    DailySummary,
    OAuthToken,
    Product,
    ProductSearchResult,
    UserProfile,
)

# Observed mobile-app credentials identify the app, not an individual account.
OAUTH_CLIENT_ID = "3_5rbw4kehpugw8ogsc8ck8oo4ogswgckcskc04gcg8kk8k48ssw"
OAUTH_CLIENT_SECRET = "25gdtt1hvdi8gwowoww4oo88sgsw0oo04o0og0kkgwwks8k0k"
OAUTH_TOKEN_PATH = "oauth/token"
USER_PATH = "user"
DAILY_SUMMARY_PATH = "user/widgets/daily-summary"
CONSUMED_ITEMS_PATH = "user/consumed-items"
PRODUCT_SEARCH_PATH = "products/search"

ResponseModelT = TypeVar("ResponseModelT", bound=BaseModel)


@dataclass
class _TokenState:
    token: OAuthToken = field(repr=False)
    expires_at: float


class YazioHttpClient:
    """Shared async HTTP client with an in-memory OAuth token cache."""

    def __init__(
        self,
        settings: Settings,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._settings = settings
        self._clock = clock
        self._token_state: _TokenState | None = None
        self._token_lock = asyncio.Lock()
        timeout = httpx.Timeout(
            settings.read_timeout_seconds,
            connect=settings.connect_timeout_seconds,
        )
        self._client = httpx.AsyncClient(
            base_url=f"{settings.api_base_url}/",
            headers={
                "Accept": "application/json",
                "User-Agent": settings.user_agent,
            },
            timeout=timeout,
        )

    @property
    def is_closed(self) -> bool:
        """Report whether the shared HTTP client has been closed."""
        return self._client.is_closed

    async def __aenter__(self) -> "YazioHttpClient":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the shared connection pool."""
        await self._client.aclose()

    async def get_access_token(self) -> str:
        """Return a valid token, refreshing or authenticating when necessary."""
        state = self._token_state
        if self._is_token_valid(state):
            assert state is not None
            return state.token.access_token.get_secret_value()

        async with self._token_lock:
            state = self._token_state
            if self._is_token_valid(state):
                assert state is not None
                return state.token.access_token.get_secret_value()

            token = await self._renew_token(state)
            self._store_token(token)
            return token.access_token.get_secret_value()

    async def get_user(self) -> UserProfile:
        """Return the authenticated user's observed profile."""
        return await self._get_model(USER_PATH, UserProfile)

    async def get_user_daily_summary(self, day: date) -> DailySummary:
        """Return the observed daily-summary widget for one calendar day."""
        return await self._get_model(
            DAILY_SUMMARY_PATH,
            DailySummary,
            params={"date": day.isoformat()},
        )

    async def get_user_consumed_items(self, day: date) -> ConsumedItems:
        """Return the three observed consumed-item buckets for one day."""
        return await self._get_model(
            CONSUMED_ITEMS_PATH,
            ConsumedItems,
            params={"date": day.isoformat()},
        )

    async def search_products(
        self,
        query: str,
        *,
        sex: str,
        countries: str,
        locales: str | None = None,
    ) -> list[ProductSearchResult]:
        """Search products with the parameters observed as required by YAZIO."""
        params = {"query": query, "sex": sex, "countries": countries}
        headers: dict[str, str] | None = None
        if locales is not None:
            params["locales"] = locales
            headers = {"Accept-Language": locales}
        payload = await self._get_json(
            PRODUCT_SEARCH_PATH,
            params=params,
            headers=headers,
        )
        try:
            return TypeAdapter(list[ProductSearchResult]).validate_python(payload)
        except ValidationError:
            raise YazioInvalidResponseError() from None

    async def get_product(self, product_id: str) -> Product:
        """Return one product by its observed YAZIO identifier."""
        encoded_id = quote(product_id, safe="")
        return await self._get_model(f"products/{encoded_id}", Product)

    async def _get_model(
        self,
        path: str,
        model: type[ResponseModelT],
        *,
        params: Mapping[str, str] | None = None,
    ) -> ResponseModelT:
        payload = await self._get_json(path, params=params)
        try:
            return model.model_validate(payload)
        except ValidationError:
            raise YazioInvalidResponseError() from None

    async def _get_json(
        self,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        access_token = await self.get_access_token()
        request_headers = {"Authorization": f"Bearer {access_token}"}
        if headers is not None:
            request_headers.update(headers)
        try:
            response = await self._client.get(
                path,
                params=params,
                headers=request_headers,
            )
        except httpx.HTTPError:
            raise YazioTransportError() from None

        if response.is_error:
            self._raise_http_error(response)
        try:
            return response.json()
        except ValueError:
            raise YazioInvalidResponseError(status_code=response.status_code) from None

    def _is_token_valid(self, state: _TokenState | None) -> bool:
        return state is not None and self._clock() < state.expires_at

    async def _renew_token(self, state: _TokenState | None) -> OAuthToken:
        refresh_token = None if state is None else state.token.refresh_token
        if refresh_token is not None:
            try:
                refreshed = await self._request_token(
                    {
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token.get_secret_value(),
                        "client_id": OAUTH_CLIENT_ID,
                        "client_secret": OAUTH_CLIENT_SECRET,
                    }
                )
            except YazioAuthenticationError:
                pass
            else:
                if refreshed.refresh_token is None:
                    refreshed = refreshed.model_copy(
                        update={"refresh_token": refresh_token}
                    )
                return refreshed

        return await self._request_token(
            {
                "username": self._settings.username.get_secret_value(),
                "password": self._settings.password.get_secret_value(),
                "grant_type": "password",
                "client_id": OAUTH_CLIENT_ID,
                "client_secret": OAUTH_CLIENT_SECRET,
            }
        )

    async def _request_token(self, payload: Mapping[str, str]) -> OAuthToken:
        try:
            response = await self._client.post(OAUTH_TOKEN_PATH, json=payload)
        except httpx.HTTPError:
            raise YazioTransportError() from None

        if response.is_error:
            self._raise_http_error(response, authentication_request=True)

        try:
            return OAuthToken.model_validate(response.json())
        except (ValueError, ValidationError):
            raise YazioInvalidResponseError(status_code=response.status_code) from None

    def _raise_http_error(
        self,
        response: httpx.Response,
        *,
        authentication_request: bool = False,
    ) -> None:
        try:
            payload = response.json()
        except ValueError:
            payload = None

        if isinstance(payload, dict) and payload.get("error") == "version_blocked":
            raise YazioVersionBlockedError(status_code=response.status_code)
        if response.status_code == 401 or (
            authentication_request and response.status_code == 400
        ):
            raise YazioAuthenticationError(status_code=response.status_code)
        raise YazioHttpError(status_code=response.status_code)

    def _store_token(self, token: OAuthToken) -> None:
        lifetime = max(token.expires_in, 0.0)
        self._token_state = _TokenState(
            token=token,
            expires_at=self._clock() + lifetime,
        )
