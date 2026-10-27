import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from yazio_mcp.models import (
    ConsumedItems,
    ConsumedProduct,
    DailySummary,
    OAuthToken,
    Product,
    ProductSearchResult,
    SimpleProduct,
    UserProfile,
)

FIXTURES = Path(__file__).parents[1] / "fixtures"


def load_fixture(name: str) -> dict[str, Any]:
    with (FIXTURES / name).open(encoding="utf-8") as fixture:
        value: dict[str, Any] = json.load(fixture)
    return value


def test_auth_fixture_hides_tokens_and_allows_unknown_fields() -> None:
    token = OAuthToken.model_validate(load_fixture("oauth_token.json"))

    assert token.access_token.get_secret_value() == "sanitized-access-token"
    assert token.refresh_token is not None
    assert token.refresh_token.get_secret_value() == "sanitized-refresh-token"
    assert token.model_extra == {"observed_extension": "accepted"}
    assert "sanitized-access-token" not in repr(token)
    assert "sanitized-refresh-token" not in token.model_dump_json()


def test_auth_validation_error_does_not_echo_token() -> None:
    secret = "must-not-appear-in-errors"

    try:
        OAuthToken.model_validate({"access_token": secret, "expires_in": secret})
    except ValidationError as error:
        assert secret not in str(error)
    else:
        raise AssertionError("invalid expires_in should fail validation")


def test_user_fixture_parses_dates_secrets_and_unknown_fields() -> None:
    user = UserProfile.model_validate(load_fixture("user_profile.json"))

    assert user.date_of_birth == date(2000, 1, 1)
    assert user.email is not None
    assert user.email.get_secret_value() == "sanitized@example.invalid"
    assert user.diet is not None
    assert user.diet.model_extra == {"observed_extension": True}
    assert user.model_extra == {"observed_extension": "accepted"}
    assert "sanitized@example.invalid" not in repr(user)


def test_product_fixture_parses_timestamp_and_unknown_fields() -> None:
    product = Product.model_validate(load_fixture("product.json"))

    assert product.nutrients["energy.energy"] == 1.25
    assert product.servings[0].model_extra == {"observed_extension": "accepted"}
    assert product.updated_at == datetime(2026, 10, 1, 12, 30, tzinfo=timezone.utc)
    assert product.model_extra == {"observed_extension": "accepted"}


def test_product_search_fixture_allows_unknown_fields() -> None:
    result = ProductSearchResult.model_validate(
        load_fixture("product_search_result.json")
    )

    assert result.product_id == "00000000-0000-0000-0000-000000000006"
    assert result.nutrients["energy.energy"] == 1.5
    assert result.model_extra == {"observed_extension": "accepted"}


def test_consumed_items_keep_buckets_separate_and_normalize_timestamps() -> None:
    items = ConsumedItems.model_validate(load_fixture("consumed_items.json"))

    assert items.products[0].date == datetime(2026, 8, 2, 16, 2, 48)
    assert isinstance(items.simple_products[0], SimpleProduct)
    assert items.simple_products[0].model_extra == {
        "id": "00000000-0000-0000-0000-000000000003",
        "name": "Sanitized manual entry",
    }
    assert items.recipe_portions[0].date == datetime(2026, 8, 2, 19, 30)
    assert items.model_extra == {"observed_extension": "accepted"}


def test_consumed_items_partial_response_gets_independent_empty_lists() -> None:
    first = ConsumedItems.model_validate({})
    second = ConsumedItems.model_validate({})

    first.products.append(ConsumedProduct())

    assert len(first.products) == 1
    assert second.products == []
    assert first.simple_products == []
    assert first.recipe_portions == []


def test_daily_summary_maps_dotted_keys_and_allows_extensions() -> None:
    summary = DailySummary.model_validate(load_fixture("daily_summary.json"))

    assert summary.goals is not None
    assert summary.goals.energy == 2000
    assert summary.goals.carbohydrate == 250
    assert summary.goals.steps == 10000
    assert summary.meals is not None
    assert summary.meals.breakfast is not None
    assert summary.meals.breakfast.nutrients is not None
    assert summary.meals.breakfast.nutrients.protein == 25
    assert summary.meals.breakfast.nutrients.model_extra == {
        "observed_extension": "accepted"
    }
    assert summary.model_extra == {"observed_extension": "accepted"}
