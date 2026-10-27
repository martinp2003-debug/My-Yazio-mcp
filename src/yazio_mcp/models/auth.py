"""Authentication response models."""

from pydantic import SecretStr

from yazio_mcp.models.base import YazioResponseModel


class OAuthToken(YazioResponseModel):
    """OAuth token data observed from the private YAZIO API."""

    access_token: SecretStr
    expires_in: float
    refresh_token: SecretStr | None = None
    token_type: str | None = None
