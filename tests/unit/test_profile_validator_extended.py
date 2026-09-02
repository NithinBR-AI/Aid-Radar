"""Edge cases for profile_validator not covered in base tests."""
import pytest
from src.guardrails.profile_validator import validate_profile, ProfileValidationError, safe_serialize

VALID = {
    "state": "CA",
    "monthly_income": 2000,
    "adults": [{"age": 32, "income": 24000}],
    "children": [],
}


def test_adults_not_list_raises():
    with pytest.raises(ProfileValidationError, match="list"):
        validate_profile({**VALID, "adults": "not a list"})


def test_children_not_list_raises():
    with pytest.raises(ProfileValidationError, match="list"):
        validate_profile({**VALID, "children": "not a list"})


def test_adult_not_dict_raises():
    with pytest.raises(ProfileValidationError):
        validate_profile({**VALID, "adults": ["not a dict"]})


def test_child_not_dict_raises():
    with pytest.raises(ProfileValidationError):
        validate_profile({**VALID, "children": ["not a dict"]})


def test_household_over_20_raises():
    adults = [{"age": 30, "income": 0}] * 21
    with pytest.raises(ProfileValidationError, match="maximum"):
        validate_profile({**VALID, "adults": adults})


def test_income_over_max_raises():
    with pytest.raises(ProfileValidationError, match="<="):
        validate_profile({**VALID, "monthly_income": 600_000})


def test_ny_state_normalized():
    result = validate_profile({**VALID, "state": "New York"})
    assert result["state"] == "NY"


def test_tx_state_normalized():
    result = validate_profile({**VALID, "state": "Texas"})
    assert result["state"] == "TX"


def test_safe_serialize_int():
    try:
        import numpy as np
        assert safe_serialize(np.int64(42)) == 42
    except ImportError:
        pytest.skip("numpy not installed")


def test_safe_serialize_unknown_type_raises():
    with pytest.raises(TypeError):
        safe_serialize(object())


def test_zero_income_valid():
    result = validate_profile({**VALID, "monthly_income": 0})
    assert result["monthly_income"] == 0.0


def test_account_number_scrubbed():
    p = {**VALID, "notes": "Account 123456789012"}
    result = validate_profile(p)
    assert "123456789012" not in str(result)


def test_citizenship_daca_normalizes_to_qualified_immigrant():
    # DACA holders are not in the normalization map — should fall to qualified_immigrant,
    # NOT us_citizen, to avoid falsely granting full citizen program eligibility.
    p = {**VALID, "citizenship_status": "daca"}
    result = validate_profile(p)
    assert result["citizenship_status"] == "qualified_immigrant"


def test_citizenship_refugee_normalizes_to_qualified_immigrant():
    p = {**VALID, "citizenship_status": "refugee"}
    result = validate_profile(p)
    assert result["citizenship_status"] == "qualified_immigrant"


def test_citizenship_unrecognized_string_defaults_to_qualified_immigrant():
    p = {**VALID, "citizenship_status": "some unexpected string"}
    result = validate_profile(p)
    assert result["citizenship_status"] == "qualified_immigrant"


def test_citizenship_us_citizen_canonical():
    p = {**VALID, "citizenship_status": "US citizen"}
    result = validate_profile(p)
    assert result["citizenship_status"] == "us_citizen"


def test_citizenship_green_card_normalizes():
    p = {**VALID, "citizenship_status": "green card"}
    result = validate_profile(p)
    assert result["citizenship_status"] == "permanent_resident"


def test_out_of_state_raises():
    p = {**VALID, "state": "XX"}
    with pytest.raises(ProfileValidationError, match="Unrecognized or unsupported state"):
        validate_profile(p)


def test_supported_state_valid():
    result = validate_profile(VALID)
    assert result["state"] == "CA"


def test_household_size_clamped_to_max_20():
    result = validate_profile({**VALID, "household_size": 100})
    assert result["household_size"] == 20


def test_household_size_negative_clamped_to_1():
    result = validate_profile({**VALID, "household_size": -5})
    assert result["household_size"] == 1


def test_household_size_string_coerced():
    result = validate_profile({**VALID, "household_size": "4"})
    assert result["household_size"] == 4


def test_household_size_bad_value_defaults_to_1():
    result = validate_profile({**VALID, "household_size": "abc"})
    assert result["household_size"] == 1


def test_citizenship_declined_returns_none():
    result = validate_profile({**VALID, "citizenship_status": "declined"})
    assert result["citizenship_status"] is None


def test_citizenship_prefer_not_to_say_returns_none():
    result = validate_profile({**VALID, "citizenship_status": "prefer not to say"})
    assert result["citizenship_status"] is None
