"""Shared behavior for models parsed from private YAZIO responses."""

from pydantic import BaseModel, ConfigDict


class YazioResponseModel(BaseModel):
    """Accept observed API extensions and avoid echoing invalid input."""

    model_config = ConfigDict(extra="allow", hide_input_in_errors=True)
