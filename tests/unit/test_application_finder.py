import json
from unittest.mock import patch, mock_open
import pytest

from src.tools.application_finder import application_finder

SNAP_DATA = {
    "name": "SNAP",
    "agency": "USDA",
    "application": {
        "federal_url": "https://www.fns.usda.gov/snap/apply",
        "state_urls": {"CA": "https://benefitscal.com", "TX": "https://yourtexasbenefits.com"},
        "notes": "Apply online or at your local office.",
    },
    "documents_needed": ["Photo ID", "Proof of income"],
    "state_overrides": {},
}


def _mock_load(data):
    return patch(
        "src.tools.application_finder._load_program",
        return_value=data,
    )


def test_state_specific_url_returned():
    with _mock_load(SNAP_DATA):
        result = application_finder("snap", "CA")
    assert result["status"] == "success"
    assert result["content"][0]["json"]["apply_url"] == "https://benefitscal.com"
    assert result["content"][0]["json"]["url_source"] == "state_specific"


def test_federal_fallback_when_no_state_url():
    with _mock_load(SNAP_DATA):
        result = application_finder("snap", "WA")
    data = result["content"][0]["json"]
    assert data["url_source"] == "federal_fallback"
    assert "fns.usda.gov" in data["apply_url"]


def test_file_not_found_returns_error():
    with patch("src.tools.application_finder._load_program", side_effect=FileNotFoundError):
        result = application_finder("nonexistent_program", "CA")
    assert result["status"] == "error"


def test_state_uppercased():
    with _mock_load(SNAP_DATA):
        result = application_finder("snap", "ca")
    assert result["content"][0]["json"]["state"] == "CA"


def test_documents_returned():
    with _mock_load(SNAP_DATA):
        result = application_finder("snap", "CA")
    docs = result["content"][0]["json"]["documents_needed"]
    assert "Photo ID" in docs


def test_no_url_available():
    data = {**SNAP_DATA, "application": {"state_urls": {}, "notes": ""}}
    with _mock_load(data):
        result = application_finder("snap", "CA")
    assert result["content"][0]["json"]["url_source"] == "none"
    assert result["content"][0]["json"]["apply_url"] is None


def test_corrupt_json_returns_error():
    with patch("src.tools.application_finder._load_program", side_effect=FileNotFoundError("corrupt")):
        result = application_finder("snap", "CA")
    assert result["status"] == "error"
