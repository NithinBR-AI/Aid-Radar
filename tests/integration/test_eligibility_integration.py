"""
Integration tests — hit real PolicyEngine, no mocks, no LLM calls.
Run with: pytest tests/integration/test_eligibility_integration.py -v
"""
import json
import pytest
from src.tools.eligibility_checker import eligibility_checker

# CA family of 3, $2000/mo — should qualify for SNAP
CA_FAMILY = json.dumps({
    "state": "CA",
    "monthly_income": 2000,
    "adults": [{"age": 32, "income": 24000}],
    "children": [{"age": 4}, {"age": 8}],
})

# TX single adult, $6000/mo — too high for most programs
TX_HIGH_INCOME = json.dumps({
    "state": "TX",
    "monthly_income": 6000,
    "adults": [{"age": 40, "income": 72000}],
    "children": [],
})

# FL elderly single, $900/mo — should qualify for SSI/Medicaid
FL_ELDERLY = json.dumps({
    "state": "FL",
    "monthly_income": 900,
    "adults": [{"age": 70, "income": 10800}],
    "children": [],
})


def test_ca_family_returns_success():
    result = eligibility_checker(CA_FAMILY)
    assert result["status"] == "success"


def test_ca_family_snap_eligible():
    result = eligibility_checker(CA_FAMILY)
    programs = result["content"][0]["json"]["programs"]
    assert programs["snap"]["eligible"] is True


def test_ca_family_snap_benefit_is_numeric():
    result = eligibility_checker(CA_FAMILY)
    programs = result["content"][0]["json"]["programs"]
    benefit = programs["snap"].get("estimated_benefit")
    if benefit:
        assert isinstance(benefit.get("monthly"), float)


def test_tx_high_income_snap_ineligible():
    result = eligibility_checker(TX_HIGH_INCOME)
    assert result["status"] == "success"
    programs = result["content"][0]["json"]["programs"]
    assert programs["snap"]["eligible"] is False


def test_fl_elderly_medicaid_checked():
    result = eligibility_checker(FL_ELDERLY)
    assert result["status"] == "success"
    programs = result["content"][0]["json"]["programs"]
    assert "medicaid" in programs


def test_all_8_programs_always_present():
    result = eligibility_checker(CA_FAMILY)
    programs = result["content"][0]["json"]["programs"]
    expected = {"snap", "medicaid", "wic", "tanf", "ssi", "lifeline", "free_school_meals", "liheap"}
    assert expected == set(programs.keys())


def test_veteran_flag_propagated():
    profile = json.dumps({
        "state": "CA",
        "monthly_income": 1500,
        "adults": [{"age": 45, "income": 18000}],
        "children": [],
        "veteran_in_household": True,
    })
    result = eligibility_checker(profile)
    summary = result["content"][0]["json"]["summary"]
    assert summary["veteran_in_household"] is True
