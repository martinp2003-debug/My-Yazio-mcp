"""HTTP adapter and in-memory OAuth lifecycle for the private YAZIO API."""

import asyncio
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import TracebackType

import httpx
from pydantic import ValidationError

from yazio_mcp.config import Settings
from yazio_mcp.errors import (
    YazioAuthenticationError,
    YazioHttpError,
    YazioInvalidResponseError,
    YazioTransportError,
    YazioVersionBlockedError,
)
from yazio_mcp.models import OAuthToken

# Observed mobile-app credentials identify the app, not an individual account.
OAUTH_CLIENT_ID = "3_5rbw4kehpugw8ogsc8ck8oo4ogswgckcskc04gcg8kk8k48ssw"
OAUTH_CLIENT_SECRET = "25gdtt1hvdi8gwowoww4oo88sgsw0oo04o0og0kkgwwks8k0k"
OAUTH_TOKEN_PATH = "oauth/token"


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
            self._raise_http_error(response)

        try:
            return OAuthToken.model_validate(response.json())
        except (ValueError, ValidationError):
            raise YazioInvalidResponseError(status_code=response.status_code) from None

    def _raise_http_error(self, response: httpx.Response) -> None:
        try:
            payload = response.json()
        except ValueError:
            payload = None

        if isinstance(payload, dict) and payload.get("error") == "version_blocked":
            raise YazioVersionBlockedError(status_code=response.status_code)
        if response.status_code in {400, 401}:
            raise YazioAuthenticationError(status_code=response.status_code)
        raise YazioHttpError(status_code=response.status_code)

    def _store_token(self, token: OAuthToken) -> None:
        lifetime = max(token.expires_in, 0.0)
        self._token_state = _TokenState(
            token=token,
            expires_at=self._clock() + lifetime,
        )
