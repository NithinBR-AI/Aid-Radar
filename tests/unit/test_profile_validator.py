import pytest
from src.guardrails.profile_validator import validate_profile, ProfileValidationError

VALID = {
    "state": "CA",
    "monthly_income": 2000,
    "adults": [{"age": 32, "income": 24000}],
    "children": [{"age": 4}],
}


def test_valid_profile_passes():
    result = validate_profile(VALID)
    assert result["state"] == "CA"
    assert result["monthly_income"] == 2000.0


def test_state_normalized_lowercase():
    p = {**VALID, "state": "ca"}
    assert validate_profile(p)["state"] == "CA"


def test_state_normalized_full_name():
    p = {**VALID, "state": "California"}
    assert validate_profile(p)["state"] == "CA"


def test_unsupported_state_falls_back_to_federal():
    # Out-of-area states no longer raise — they fall back to federal thresholds
    # so the intake prompt's promise ("we'll use federal thresholds") is kept.
    p = {**VALID, "state": "OH"}
    result = validate_profile(p)
    assert result["state"] == "CA"  # FEDERAL_FALLBACK_STATE
    assert result["state_is_fallback"] is True
    assert result["state_original"] == "OH"


def test_missing_state_raises():
    p = {k: v for k, v in VALID.items() if k != "state"}
    with pytest.raises(ProfileValidationError, match="required"):
        validate_profile(p)


def test_income_string_coerced():
    p = {**VALID, "monthly_income": "$2,500/mo"}
    assert validate_profile(p)["monthly_income"] == 2500.0


def test_negative_income_raises():
    p = {**VALID, "monthly_income": -100}
    with pytest.raises(ProfileValidationError, match=">="):
        validate_profile(p)


def test_empty_household_raises():
    p = {**VALID, "adults": [], "children": []}
    with pytest.raises(ProfileValidationError, match="at least 1"):
        validate_profile(p)


def test_pii_scrubbed_from_strings():
    p = {**VALID, "notes": "SSN: 123-45-6789"}
    result = validate_profile(p)
    assert "123-45-6789" not in str(result)
    assert "[REDACTED]" in str(result)


def test_non_dict_raises():
    with pytest.raises(ProfileValidationError, match="JSON object"):
        validate_profile("not a dict")


def test_children_age_coerced():
    p = {**VALID, "children": [{"age": "5"}]}
    result = validate_profile(p)
    assert result["children"][0]["age"] == 5
