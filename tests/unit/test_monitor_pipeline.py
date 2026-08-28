from unittest.mock import patch, MagicMock
from src.pipeline.monitor_pipeline import _diff_snapshots, run_monitor_check

SNAP = {"display_name": "SNAP", "eligible": True, "estimated_benefit": {"monthly": 300}}
MEDICAID = {"display_name": "Medicaid", "eligible": True, "estimated_benefit": None}


def test_gained_when_newly_eligible():
    prev = {"snap": {**SNAP, "eligible": False}}
    curr = {"snap": SNAP}
    gained, lost, changed = _diff_snapshots(prev, curr)
    assert "SNAP" in gained
    assert not lost
    assert not changed


def test_lost_when_no_longer_eligible():
    prev = {"snap": SNAP}
    curr = {"snap": {**SNAP, "eligible": False}}
    gained, lost, changed = _diff_snapshots(prev, curr)
    assert "SNAP" in lost
    assert not gained
    assert not changed


def test_changed_when_amount_differs_significantly():
    # $300 → $400 = 33% change, well above 10% threshold
    prev = {"snap": {**SNAP, "estimated_benefit": {"monthly": 300}}}
    curr = {"snap": {**SNAP, "estimated_benefit": {"monthly": 400}}}
    gained, lost, changed = _diff_snapshots(prev, curr)
    assert not gained
    assert not lost
    assert len(changed) == 1
    name, prev_amt, curr_amt = changed[0]
    assert prev_amt == 300
    assert curr_amt == 400


def test_no_change_when_amounts_same():
    prev = {"snap": SNAP}
    curr = {"snap": SNAP}
    gained, lost, changed = _diff_snapshots(prev, curr)
    assert not gained
    assert not lost
    assert not changed


def test_small_amount_change_ignored():
    # $300 → $303 = 1% change, below 10% threshold
    prev = {"snap": {**SNAP, "estimated_benefit": {"monthly": 300}}}
    curr = {"snap": {**SNAP, "estimated_benefit": {"monthly": 303}}}
    _, _, changed = _diff_snapshots(prev, curr)
    assert not changed


def test_new_program_in_current_treated_as_gained():
    prev = {}
    curr = {"snap": SNAP}
    gained, lost, changed = _diff_snapshots(prev, curr)
    assert "SNAP" in gained


def test_program_removed_from_current_treated_as_lost():
    prev = {"snap": SNAP}
    curr = {}
    gained, lost, changed = _diff_snapshots(prev, curr)
    assert "SNAP" in lost


def test_both_ineligible_no_change():
    prev = {"snap": {**SNAP, "eligible": False}}
    curr = {"snap": {**SNAP, "eligible": False}}
    gained, lost, changed = _diff_snapshots(prev, curr)
    assert not gained and not lost and not changed


def test_exactly_threshold_change_ignored():
    # $300 → $330 = exactly 10% — must NOT trigger (threshold is strictly > 10%)
    prev = {"snap": {**SNAP, "estimated_benefit": {"monthly": 300}}}
    curr = {"snap": {**SNAP, "estimated_benefit": {"monthly": 330}}}
    _, _, changed = _diff_snapshots(prev, curr)
    assert not changed


def test_one_above_threshold_triggers():
    # $300 → $331 = 10.33% — must trigger
    prev = {"snap": {**SNAP, "estimated_benefit": {"monthly": 300}}}
    curr = {"snap": {**SNAP, "estimated_benefit": {"monthly": 331}}}
    _, _, changed = _diff_snapshots(prev, curr)
    assert len(changed) == 1


# ---------------------------------------------------------------------------
# run_monitor_check — intake-schema profile validation
# ---------------------------------------------------------------------------

INTAKE_SCHEMA_PROFILE = {
    "state": "TX",
    "household_size": 5,
    "monthly_income": 8000,
    "income_is_approximate": False,
    "applicant_age": 36,
    "elderly_count": 1,
    "has_disabled_member": False,
    "has_pregnant_member": False,
    "children_under_5": [{"age": 2}],
    "children_k12": [],
    "veteran_in_household": False,
    "current_programs": [],
    "citizenship_status": None,
}


def test_run_monitor_check_accepts_intake_schema_profile():
    """Intake-schema profiles (applicant_age + children_under_5, no adults list)
    must not fail with 'Household must have at least 1 member' — build_eligibility_profile
    converts them before validation."""
    success_raw = {
        "status": "success",
        "content": [{"json": {"programs": {"snap": {"eligible": True, "display_name": "SNAP", "estimated_benefit": {"monthly": 300}}}}}],
    }
    with patch("src.pipeline.monitor_pipeline.get_profile") as mock_get, \
         patch("src.pipeline.monitor_pipeline.was_recently_notified", return_value=False), \
         patch("src.pipeline.monitor_pipeline.eligibility_checker", return_value=success_raw), \
         patch("src.pipeline.monitor_pipeline.update_snapshot"), \
         patch("src.pipeline.monitor_pipeline.create_monitor_agent", return_value=MagicMock()), \
         patch("src.pipeline.monitor_pipeline._call_agent_with_timeout", return_value="No significant changes."):

        baseline = {"snap": {"eligible": True, "display_name": "SNAP", "estimated_benefit": {"monthly": 300}}}
        mock_get.return_value = None
        result = run_monitor_check("fake-profile-id", INTAKE_SCHEMA_PROFILE, baseline)

    assert result.error is None or "Household must have" not in (result.error or "")
