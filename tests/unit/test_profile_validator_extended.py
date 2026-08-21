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


def test_out_of_state_sets_fallback_flags():
    p = {**VALID, "state": "WA"}
    result = validate_profile(p)
    assert result["state_is_fallback"] is True
    assert result["state_original"] == "WA"
    assert result["state"] == "CA"


def test_supported_state_no_fallback_flag():
    result = validate_profile(VALID)
    assert result.get("state_is_fallback") is not True
