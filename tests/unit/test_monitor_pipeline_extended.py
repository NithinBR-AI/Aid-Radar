"""Extended tests for run_monitor_check — mocked agents and DynamoDB."""
from unittest.mock import patch, MagicMock

from src.pipeline.monitor_pipeline import run_monitor_check

INTAKE = {
    "state": "CA", "monthly_income": 2000,
    "adults": [{"age": 32, "income": 24000}],
    "children": [{"age": 4}],
}

BASELINE = {
    "snap": {"display_name": "SNAP", "eligible": True, "estimated_benefit": {"monthly": 300}},
    "medicaid": {"display_name": "Medicaid", "eligible": False, "estimated_benefit": None},
}

SUCCESS_RAW = {
    "status": "success",
    "content": [{"json": {"programs": BASELINE}}],
}

_EC = "src.pipeline.monitor_pipeline.eligibility_checker"
_GP = "src.pipeline.monitor_pipeline.get_profile"
_US = "src.pipeline.monitor_pipeline.update_snapshot"
_CA = "src.pipeline.monitor_pipeline.create_monitor_agent"
_CWT = "src.pipeline.monitor_pipeline._call_agent_with_timeout"


def test_no_changes_no_agent_call():
    with patch(_EC, return_value=SUCCESS_RAW), \
         patch(_GP, return_value=None), \
         patch(_US), \
         patch(_CA), \
         patch(_CWT) as mock_cwt:
        result = run_monitor_check(None, INTAKE, BASELINE)
    assert result.error is None
    assert not result.gained and not result.lost and not result.changed
    mock_cwt.assert_not_called()


def test_eligibility_check_failure_returns_error():
    with patch(_EC, return_value={"status": "error"}), \
         patch(_GP, return_value=None), patch(_US), patch(_CA):
        result = run_monitor_check(None, INTAKE, BASELINE)
    assert result.error is not None


def test_gained_program_triggers_agent():
    new_snap = {
        **BASELINE,
        "medicaid": {"display_name": "Medicaid", "eligible": True, "estimated_benefit": None},
    }
    raw = {"status": "success", "content": [{"json": {"programs": new_snap}}]}
    with patch(_EC, return_value=raw), \
         patch(_GP, return_value=None), \
         patch(_US), \
         patch(_CA), \
         patch(_CWT, return_value="You gained Medicaid.") as mock_cwt:
        result = run_monitor_check(None, INTAKE, BASELINE)
    assert "Medicaid" in result.gained
    mock_cwt.assert_called_once()
    assert result.agent_output == "You gained Medicaid."


def test_lost_program_detected():
    new_snap = {
        **BASELINE,
        "snap": {"display_name": "SNAP", "eligible": False, "estimated_benefit": None},
    }
    raw = {"status": "success", "content": [{"json": {"programs": new_snap}}]}
    with patch(_EC, return_value=raw), \
         patch(_GP, return_value=None), \
         patch(_US), \
         patch(_CA), \
         patch(_CWT, return_value="You lost SNAP."):
        result = run_monitor_check(None, INTAKE, BASELINE)
    assert "SNAP" in result.lost


def test_profile_id_triggers_dynamo_update():
    with patch(_EC, return_value=SUCCESS_RAW), \
         patch(_GP, return_value=None), \
         patch(_US) as mock_update, \
         patch(_CA, return_value=MagicMock()):
        run_monitor_check("profile-123", INTAKE, BASELINE)
    call_kwargs = mock_update.call_args
    assert call_kwargs[0][0] == "profile-123"  # profile_id
    assert call_kwargs[0][1] == BASELINE        # new_snapshot


def test_original_income_preserved():
    with patch(_EC, return_value=SUCCESS_RAW), \
         patch(_GP, return_value=None), \
         patch(_US), \
         patch(_CA, return_value=MagicMock()):
        result = run_monitor_check(None, INTAKE, BASELINE)
    assert result.original_income == 2000
    assert result.new_income == 2000


def test_invalid_state_returns_error():
    bad_profile = {**INTAKE, "state": "OH"}
    result = run_monitor_check(None, bad_profile, BASELINE)
    assert result.error is not None
    assert "validation" in result.error.lower()
