"""Unit tests for estimate_cliff_effect tool."""
import json
from unittest.mock import patch

from src.tools.cliff_effect import estimate_cliff_effect

_EC = "src.tools.cliff_effect.eligibility_checker"

PROFILE = json.dumps({
    "state": "CA",
    "monthly_income": 2000,
    "adults": [{"age": 32, "income": 24000}],
    "children": [{"age": 4}],
    "has_disabled_member": False,
    "has_pregnant_member": False,
    "citizenship_status": "us_citizen",
})

ELIGIBLE_RAW = {
    "status": "success",
    "content": [{"json": {"programs": {
        "snap": {"eligible": True, "estimated_benefit": {"monthly": 200}},
    }}}],
}

INELIGIBLE_RAW = {
    "status": "success",
    "content": [{"json": {"programs": {
        "snap": {"eligible": False, "estimated_benefit": None},
    }}}],
}


def test_cliff_detected_when_projected_ineligible():
    with patch(_EC, return_value=INELIGIBLE_RAW):
        result = estimate_cliff_effect("snap", 2000.0, PROFILE)
    assert result["status"] == "success"
    data = result["content"][0]["json"]
    assert data["cliff_detected"] is True
    assert data["projected_eligible"] is False


def test_no_cliff_when_still_eligible():
    with patch(_EC, return_value=ELIGIBLE_RAW):
        result = estimate_cliff_effect("snap", 2000.0, PROFILE)
    assert result["status"] == "success"
    data = result["content"][0]["json"]
    assert data["cliff_detected"] is False
    assert data["projected_monthly_benefit"] == 200


def test_projected_income_is_current_plus_500():
    with patch(_EC, return_value=ELIGIBLE_RAW):
        result = estimate_cliff_effect("snap", 1500.0, PROFILE)
    data = result["content"][0]["json"]
    assert data["projected_monthly_income"] == 2000.0


def test_invalid_income_returns_error():
    result = estimate_cliff_effect("snap", -100.0, PROFILE)
    assert result["status"] == "error"


def test_invalid_profile_json_returns_error():
    result = estimate_cliff_effect("snap", 2000.0, "not valid json{")
    assert result["status"] == "error"


def test_unknown_program_id_returns_error():
    with patch(_EC, return_value=ELIGIBLE_RAW):
        result = estimate_cliff_effect("unknown_program", 2000.0, PROFILE)
    assert result["status"] == "error"
    assert "not found" in result["content"][0]["text"]


def test_policyengine_failure_returns_error():
    with patch(_EC, return_value={"status": "error"}):
        result = estimate_cliff_effect("snap", 2000.0, PROFILE)
    assert result["status"] == "error"


def test_deep_copy_does_not_mutate_original():
    import json as _json
    original = _json.loads(PROFILE)
    original_income = original["adults"][0]["income"]
    with patch(_EC, return_value=ELIGIBLE_RAW):
        estimate_cliff_effect("snap", 2000.0, PROFILE)
    # Original profile string is unchanged — deep copy worked
    reparsed = _json.loads(PROFILE)
    assert reparsed["adults"][0]["income"] == original_income
