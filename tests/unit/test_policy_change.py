"""Unit tests for check_policy_change tool."""
import json
from unittest.mock import patch, mock_open

from src.tools.policy_change import check_policy_change

CHANGELOG = {
    "snap": [
        {
            "date": "2024-10-01",
            "states": ["ALL"],
            "change": "Benefit tables updated.",
            "impact": "benefit_amount_change",
            "source": "USDA FNS",
        },
        {
            "date": "2023-01-01",
            "states": ["CA"],
            "change": "CA-specific rule change.",
            "impact": "eligibility_rule_change",
            "source": "CA DSS",
        },
    ],
    "medicaid": [],
}

_LOAD = "src.tools.policy_change._load_changelog"


def test_returns_changes_after_date():
    with patch(_LOAD, return_value=CHANGELOG):
        result = check_policy_change("snap", "CA", "2024-01-01")
    assert result["status"] == "success"
    data = result["content"][0]["json"]
    assert data["changes_found"] == 1
    assert data["policy_driven"] is True


def test_returns_empty_when_no_changes_after_date():
    with patch(_LOAD, return_value=CHANGELOG):
        result = check_policy_change("snap", "CA", "2025-01-01")
    data = result["content"][0]["json"]
    assert data["changes_found"] == 0
    assert data["policy_driven"] is False


def test_all_states_wildcard_matches_any_state():
    with patch(_LOAD, return_value=CHANGELOG):
        result = check_policy_change("snap", "TX", "2024-01-01")
    data = result["content"][0]["json"]
    # The ALL entry (2024-10-01) should match TX
    assert data["changes_found"] == 1


def test_state_specific_entry_does_not_match_other_state():
    with patch(_LOAD, return_value=CHANGELOG):
        result = check_policy_change("snap", "TX", "2022-01-01")
    data = result["content"][0]["json"]
    # Only the ALL entry (2024-10-01) and no CA-only entries should match TX
    assert all("CA" not in e.get("states", []) or "ALL" in e.get("states", [])
               for e in data["changes"])


def test_unknown_program_returns_error():
    with patch(_LOAD, return_value=CHANGELOG):
        result = check_policy_change("nonexistent", "CA", "2024-01-01")
    assert result["status"] == "error"
    assert "Unknown program_id" in result["content"][0]["text"]


def test_invalid_date_format_returns_error():
    with patch(_LOAD, return_value=CHANGELOG):
        result = check_policy_change("snap", "CA", "01/01/2024")
    assert result["status"] == "error"
    assert "YYYY-MM-DD" in result["content"][0]["text"]


def test_changelog_load_failure_returns_error():
    with patch(_LOAD, side_effect=RuntimeError("file missing")):
        result = check_policy_change("snap", "CA", "2024-01-01")
    assert result["status"] == "error"


def test_program_with_no_entries_returns_empty():
    with patch(_LOAD, return_value=CHANGELOG):
        result = check_policy_change("medicaid", "CA", "2024-01-01")
    data = result["content"][0]["json"]
    assert data["changes_found"] == 0
    assert data["policy_driven"] is False
