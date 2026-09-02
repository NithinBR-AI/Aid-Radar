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


def test_unsupported_state_raises():
    p = {**VALID, "state": "XX"}
    with pytest.raises(ProfileValidationError, match="Unrecognized or unsupported state"):
        validate_profile(p)


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


def test_all_50_states_accepted():
    for code in [
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
        "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
        "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
        "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
        "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    ]:
        p = {**VALID, "state": code}
        assert validate_profile(p)["state"] == code, f"State {code} should be accepted"


def test_full_state_names_all_50():
    name_to_code = {
        "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
        "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
        "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
        "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
        "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
        "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
        "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
        "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
        "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
        "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
        "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
        "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
        "Wisconsin": "WI", "Wyoming": "WY",
    }
    for name, code in name_to_code.items():
        p = {**VALID, "state": name}
        assert validate_profile(p)["state"] == code, f"'{name}' should map to {code}"


def test_children_age_coerced():
    p = {**VALID, "children": [{"age": "5"}]}
    result = validate_profile(p)
    assert result["children"][0]["age"] == 5
