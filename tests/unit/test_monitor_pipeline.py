from src.pipeline.monitor_pipeline import _diff_snapshots

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
