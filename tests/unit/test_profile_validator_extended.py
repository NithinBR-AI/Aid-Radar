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
