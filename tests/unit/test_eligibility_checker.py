import json
from unittest.mock import patch, MagicMock
import pytest

from src.tools.eligibility_checker import eligibility_checker, _check_liheap, _build_situation

VALID_PROFILE = {
    "state": "CA",
    "monthly_income": 2000,
    "adults": [{"age": 32, "income": 24000}],
    "children": [{"age": 4}],
}


def test_invalid_json_returns_error():
    result = eligibility_checker("not json")
    assert result["status"] == "error"


def test_invalid_profile_returns_error():
    # Truly invalid profile (missing state) — should return error
    bad = json.dumps({"monthly_income": 2000, "adults": [{"age": 30, "income": 0}], "children": []})
    result = eligibility_checker(bad)
    assert result["status"] == "error"


def test_out_of_state_returns_error():
    # Unsupported states now raise ProfileValidationError — no silent fallback
    oh = json.dumps({"state": "OH", "monthly_income": 2000, "adults": [{"age": 30, "income": 0}], "children": []})
    result = eligibility_checker(oh)
    assert result["status"] == "error"


def test_validate_profile_called_before_simulation():
    with patch("src.tools.eligibility_checker.validate_profile") as mock_validate, \
         patch("src.tools.eligibility_checker.Simulation") as mock_sim:
        mock_validate.return_value = VALID_PROFILE
        mock_sim.return_value.calculate.return_value = [False]
        eligibility_checker(json.dumps(VALID_PROFILE))
        mock_validate.assert_called_once()


def test_returns_success_structure():
    with patch("src.tools.eligibility_checker.Simulation") as mock_sim:
        mock_sim.return_value.calculate.return_value = [0.0]
        result = eligibility_checker(json.dumps(VALID_PROFILE))
    assert result["status"] == "success"
    data = result["content"][0]["json"]
    assert "programs" in data
    assert "summary" in data


def test_liheap_included_in_results():
    with patch("src.tools.eligibility_checker.Simulation") as mock_sim:
        mock_sim.return_value.calculate.return_value = [0.0]
        result = eligibility_checker(json.dumps(VALID_PROFILE))
    programs = result["content"][0]["json"]["programs"]
    assert "liheap" in programs


def test_undocumented_restricted_programs_set_ineligible():
    profile = {**VALID_PROFILE, "citizenship_status": "undocumented"}
    with patch("src.tools.eligibility_checker.Simulation") as mock_sim:
        mock_sim.return_value.calculate.return_value = [1.0]
        result = eligibility_checker(json.dumps(profile))
    programs = result["content"][0]["json"]["programs"]
    assert programs["snap"]["eligible"] is False
    assert programs["snap"].get("citizenship_override") is True


def test_check_liheap_eligible_low_income():
    profile = {**VALID_PROFILE, "monthly_income": 500}
    result = _check_liheap(profile)
    assert result["eligible"] is True


def test_check_liheap_ineligible_high_income():
    profile = {**VALID_PROFILE, "monthly_income": 10000}
    result = _check_liheap(profile)
    assert result["eligible"] is False


def test_build_situation_creates_correct_structure():
    situation = _build_situation(VALID_PROFILE)
    assert "people" in situation
    assert "households" in situation
    assert "adult_0" in situation["people"]
    assert "child_0" in situation["people"]
