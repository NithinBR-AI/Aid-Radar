"""Unit tests for get_profile_history tool."""
from unittest.mock import patch

from src.tools.profile_history import get_profile_history

_GP = "src.tools.profile_history.get_profile"

SNAPSHOT_A = {"snap": {"eligible": True, "estimated_benefit": {"monthly": 300}}}
SNAPSHOT_B = {"snap": {"eligible": True, "estimated_benefit": {"monthly": 280}}}
CURRENT = {"snap": {"eligible": True, "estimated_benefit": {"monthly": 260}}}

FULL_RECORD = {
    "profile_id": "abc-123",
    "profile": {"state": "CA"},
    "eligibility_snapshot": CURRENT,
    "snapshot_history": [SNAPSHOT_A, SNAPSHOT_B],
    "created_at": "2024-01-01T00:00:00+00:00",
    "updated_at": "2024-06-01T00:00:00+00:00",
    "state": "CA",
}


def test_returns_current_and_history():
    with patch(_GP, return_value=FULL_RECORD):
        result = get_profile_history("abc-123")
    assert result["status"] == "success"
    data = result["content"][0]["json"]
    assert data["current_snapshot"] == CURRENT
    assert data["snapshot_history"] == [SNAPSHOT_A, SNAPSHOT_B]
    assert data["history_count"] == 2


def test_returns_empty_history_when_none_stored():
    record = {**FULL_RECORD, "snapshot_history": []}
    with patch(_GP, return_value=record):
        result = get_profile_history("abc-123")
    data = result["content"][0]["json"]
    assert data["history_count"] == 0
    assert data["snapshot_history"] == []


def test_profile_not_found_returns_error():
    with patch(_GP, return_value=None):
        result = get_profile_history("missing-id")
    assert result["status"] == "error"
    assert "No profile found" in result["content"][0]["text"]


def test_empty_profile_id_returns_error():
    result = get_profile_history("")
    assert result["status"] == "error"


def test_none_string_profile_id_returns_error():
    result = get_profile_history("None")
    assert result["status"] == "error"
    assert "valid" in result["content"][0]["text"].lower()


def test_missing_snapshot_history_key_defaults_to_empty():
    record = {k: v for k, v in FULL_RECORD.items() if k != "snapshot_history"}
    with patch(_GP, return_value=record):
        result = get_profile_history("abc-123")
    data = result["content"][0]["json"]
    assert data["snapshot_history"] == []
    assert data["history_count"] == 0
