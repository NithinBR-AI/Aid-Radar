"""Tests for EligibilityOutput Pydantic schema and parse_eligibility_output."""
import json
import pytest
from src.models.eligibility_output import parse_eligibility_output, EligibilityOutput

VALID_OUTPUT = {
    "household_summary": {"state": "CA", "household_size": 3, "monthly_income": 2000},
    "eligible_programs": [
        {
            "program_id": "snap",
            "program_name": "SNAP",
            "eligible": True,
            "estimated_monthly_benefit": 300.0,
            "application_url": "https://benefitscal.com",
            "required_documents": ["Photo ID"],
            "cascading_benefits": [],
        }
    ],
    "ineligible_programs": [{"program_id": "ssi", "reason": "Income too high"}],
    "error_programs": [],
    "total_estimated_monthly_benefit": 300.0,
    "total_estimated_annual_benefit": 3600.0,
}


def test_valid_json_in_fenced_block():
    text = f"```json\n{json.dumps(VALID_OUTPUT)}\n```"
    result = parse_eligibility_output(text)
    assert result is not None
    assert result.household_summary.state == "CA"
    assert len(result.eligible_programs) == 1
    assert result.eligible_programs[0].program_id == "snap"


def test_valid_json_bare():
    text = f"Here is the output:\n{json.dumps(VALID_OUTPUT)}"
    result = parse_eligibility_output(text)
    assert result is not None
    assert result.total_estimated_monthly_benefit == 300.0


def test_returns_none_on_no_json():
    assert parse_eligibility_output("No JSON here.") is None


def test_returns_none_on_malformed_json():
    assert parse_eligibility_output("```json\n{bad json\n```") is None


def test_returns_none_on_missing_required_field():
    # household_summary is required — missing it should fail validation
    bad = {k: v for k, v in VALID_OUTPUT.items() if k != "household_summary"}
    text = json.dumps(bad)
    result = parse_eligibility_output(text)
    assert result is None


def test_extra_fields_stripped_not_error():
    # LLM sometimes adds fields like "notes" — should be silently ignored
    data = {**VALID_OUTPUT, "notes": "extra field", "confidence": 0.95}
    text = json.dumps(data)
    result = parse_eligibility_output(text)
    assert result is not None
    assert not hasattr(result, "notes")


def test_empty_eligible_programs_valid():
    data = {**VALID_OUTPUT, "eligible_programs": [], "total_estimated_monthly_benefit": 0}
    result = parse_eligibility_output(json.dumps(data))
    assert result is not None
    assert result.eligible_programs == []


def test_none_benefit_fields_valid():
    data = {**VALID_OUTPUT}
    data["eligible_programs"][0]["estimated_monthly_benefit"] = None
    result = parse_eligibility_output(json.dumps(data))
    assert result is not None
    assert result.eligible_programs[0].estimated_monthly_benefit is None
