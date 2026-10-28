"""Stable application errors for private YAZIO API failures."""


class YazioError(Exception):
    """Base error that never embeds response bodies or credentials."""

    code = "yazio_error"
    default_message = "YAZIO request failed"

    def __init__(self, *, status_code: int | None = None) -> None:
        self.status_code = status_code
        super().__init__(self.default_message)


class YazioAuthenticationError(YazioError):
    """Credentials or a refresh token were rejected."""

    code = "authentication_failed"
    default_message = "YAZIO authentication failed"


class YazioVersionBlockedError(YazioError):
    """The configured User-Agent identifies a retired client version."""

    code = "version_blocked"
    default_message = "YAZIO rejected the configured client version"


class YazioHttpError(YazioError):
    """YAZIO returned an unsuccessful HTTP status."""

    code = "http_error"
    default_message = "YAZIO returned an HTTP error"


class YazioTransportError(YazioError):
    """The request could not reach YAZIO or timed out."""

    code = "transport_error"
    default_message = "Could not communicate with YAZIO"


class YazioInvalidResponseError(YazioError):
    """YAZIO returned a body that does not match the observed schema."""

    code = "invalid_response"
    default_message = "YAZIO returned an invalid response"
