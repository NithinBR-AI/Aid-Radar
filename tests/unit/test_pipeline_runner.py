import json
from unittest.mock import patch, MagicMock, call

from src.pipeline.runner import extract_json_profile, build_eligibility_profile, run_whatif, run_pipeline

INTAKE_PROFILE = {
    "state": "CA",
    "household_size": 3,
    "monthly_income": 2000,
    "applicant_age": 32,
    "has_disabled_member": False,
    "has_pregnant_member": False,
    "has_elderly_65_plus": False,
    "children_under_5": [{"age": 2}],
    "children_k12": [{"age": 8}],
    "veteran_in_household": False,
    "current_programs": [],
    "citizenship_status": "us_citizen",
}


def test_extract_json_profile_from_code_block():
    text = '```json\n{"state": "CA", "monthly_income": 2000}\n```'
    result = extract_json_profile(text)
    assert result == {"state": "CA", "monthly_income": 2000}


def test_extract_json_profile_bare_json():
    text = 'Here is the profile: {"state": "TX", "monthly_income": 1500}'
    result = extract_json_profile(text)
    assert result["state"] == "TX"


def test_extract_json_profile_returns_none_on_no_json():
    assert extract_json_profile("No JSON here at all.") is None


def test_extract_json_profile_returns_none_on_invalid_json():
    assert extract_json_profile("```json\n{bad json}\n```") is None


def test_build_eligibility_profile_maps_fields():
    result = build_eligibility_profile(INTAKE_PROFILE)
    assert result["state"] == "CA"
    assert result["monthly_income"] == 2000
    assert len(result["adults"]) >= 1
    assert result["adults"][0]["age"] == 32


def test_build_eligibility_profile_children_combined():
    result = build_eligibility_profile(INTAKE_PROFILE)
    assert len(result["children"]) == 2


def test_build_eligibility_profile_pads_adults_for_household_size():
    profile = {**INTAKE_PROFILE, "household_size": 5, "children_under_5": [], "children_k12": []}
    result = build_eligibility_profile(profile)
    assert len(result["adults"]) == 5


def test_run_whatif_returns_programs():
    base = {
        "state": "CA", "monthly_income": 2000,
        "adults": [{"age": 32, "income": 24000}],
        "children": [{"age": 4}],
    }
    mock_result = {
        "status": "success",
        "content": [{"json": {"programs": {"snap": {"eligible": True}}}}]
    }
    with patch("src.pipeline.runner.eligibility_checker", return_value=mock_result):
        result = run_whatif(base, 1500, 1, 1)
    assert "snap" in result


def test_run_whatif_returns_empty_on_error():
    base = {"state": "CA", "monthly_income": 2000, "adults": [{"age": 32, "income": 24000}], "children": []}
    with patch("src.pipeline.runner.eligibility_checker", return_value={"status": "error"}):
        result = run_whatif(base, 1500, 1, 0)
    assert result == {}


# ---------------------------------------------------------------------------
# run_pipeline tests
# ---------------------------------------------------------------------------

_PROGRAMS = {"snap": {"eligible": True, "estimated_benefit": {"monthly": 300}}}
_EC_SUCCESS = {"status": "success", "content": [{"json": {"programs": _PROGRAMS}}]}

_EC = "src.pipeline.runner.eligibility_checker"
_SP = "src.pipeline.runner.save_profile"
_EA = "src.pipeline.runner.create_eligibility_agent"
_RA = "src.pipeline.runner.create_recommendation_agent"


def _make_agent(output: str):
    m = MagicMock()
    m.return_value = output
    return m


def test_run_pipeline_returns_success():
    mock_elig = _make_agent("eligibility output")
    mock_rec = _make_agent("report output")
    with patch(_EC, return_value=_EC_SUCCESS), \
         patch(_SP, return_value="pid-1"), \
         patch(_EA, return_value=mock_elig), \
         patch(_RA, return_value=mock_rec):
        result = run_pipeline(INTAKE_PROFILE)
    assert result.success
    assert result.profile_id == "pid-1"
    assert result.programs == _PROGRAMS


def test_run_pipeline_rec_prompt_contains_eligibility_profile_json():
    """Recommendation Agent must receive the eligibility_profile JSON so it can call estimate_cliff_effect."""
    mock_elig = _make_agent("eligibility output")
    mock_rec = _make_agent("report output")
    with patch(_EC, return_value=_EC_SUCCESS), \
         patch(_SP, return_value="pid-1"), \
         patch(_EA, return_value=mock_elig), \
         patch(_RA, return_value=mock_rec):
        run_pipeline(INTAKE_PROFILE)
    rec_prompt = mock_rec.call_args[0][0]
    assert "eligibility_profile" in rec_prompt.lower() or "eligibility profile" in rec_prompt.lower()
    assert "monthly_income" in rec_prompt  # eligibility_profile JSON is in the prompt


def test_run_pipeline_eligibility_checker_failure_returns_empty_programs():
    mock_elig = _make_agent("eligibility output")
    mock_rec = _make_agent("report output")
    with patch(_EC, return_value={"status": "error"}), \
         patch(_SP, return_value=None), \
         patch(_EA, return_value=mock_elig), \
         patch(_RA, return_value=mock_rec):
        result = run_pipeline(INTAKE_PROFILE)
    assert result.programs == {}


def test_run_pipeline_eligibility_agent_timeout_returns_error():
    mock_elig = MagicMock(side_effect=TimeoutError("timeout"))
    with patch(_EC, return_value=_EC_SUCCESS), \
         patch(_SP, return_value="pid-1"), \
         patch(_EA, return_value=mock_elig), \
         patch(_RA, return_value=_make_agent("report")), \
         patch("src.pipeline.runner._call_agent_with_timeout", side_effect=TimeoutError("timeout")):
        result = run_pipeline(INTAKE_PROFILE)
    assert result.error is not None
    assert "timed out" in result.error.lower()
