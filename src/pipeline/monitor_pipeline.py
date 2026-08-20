"""
Monitor Pipeline — eligibility re-check and diff logic.

Decoupled from Streamlit. Called by app.py (UI wrapper) and monitor_runner.py (cron).
"""

import json
from dataclasses import dataclass, field

from src.agents import create_monitor_agent
from src.db.profile_store import get_profile, update_snapshot
from src.pipeline.runner import build_eligibility_profile
from src.tools.eligibility_checker import eligibility_checker


@dataclass
class MonitorResult:
    original_income: int
    new_income: int
    gained: list[str] = field(default_factory=list)
    lost: list[str] = field(default_factory=list)
    changed: list[tuple] = field(default_factory=list)   # (name, prev_monthly, curr_monthly)
    agent_output: str = ""
    profile_id: str | None = None
    error: str | None = None

    @property
    def has_changes(self) -> bool:
        return bool(self.gained or self.lost or self.changed)


def _diff_snapshots(previous: dict, current: dict) -> tuple[list, list, list]:
    """Return (gained, lost, changed_amounts) between two program snapshots."""
    gained, lost, changed = [], [], []
    for pid in set(previous) | set(current):
        prev = previous.get(pid, {})
        curr = current.get(pid, {})
        name = curr.get("display_name") or prev.get("display_name") or pid.upper()
        prev_elig = prev.get("eligible", False)
        curr_elig = curr.get("eligible", False)

        if not prev_elig and curr_elig:
            gained.append(name)
        elif prev_elig and not curr_elig:
            lost.append(name)
        elif prev_elig and curr_elig:
            prev_amt = (prev.get("estimated_benefit") or {}).get("monthly", 0) or 0
            curr_amt = (curr.get("estimated_benefit") or {}).get("monthly", 0) or 0
            if abs(curr_amt - prev_amt) > 5:
                changed.append((name, prev_amt, curr_amt))

    return gained, lost, changed


def run_monitor_check(
    profile_id: str | None,
    intake_profile: dict,
    baseline_programs: dict,
) -> MonitorResult:
    """
    Re-check a saved profile against current PolicyEngine rules and generate a
    notification narrative if anything changed.

    The income passed in is the original profile income — Monitor detects FPL
    policy changes, not life events.
    """
    orig_income = int(intake_profile.get("monthly_income", 0))

    # Load from DynamoDB; fall back to in-session baseline if not found
    saved = get_profile(profile_id) if profile_id else None
    previous_snapshot = saved["eligibility_snapshot"] if saved else baseline_programs

    # Re-run eligibility at the same income — any differences are rule changes
    eligibility_profile = build_eligibility_profile(intake_profile)
    raw = eligibility_checker(json.dumps(eligibility_profile))
    if raw.get("status") != "success":
        return MonitorResult(
            original_income=orig_income,
            new_income=orig_income,
            error="Eligibility check failed",
        )

    new_snapshot = raw["content"][0]["json"]["programs"]

    if profile_id:
        update_snapshot(profile_id, new_snapshot)

    gained, lost, changed = _diff_snapshots(previous_snapshot, new_snapshot)

    if not gained and not lost and not changed:
        return MonitorResult(
            original_income=orig_income,
            new_income=orig_income,
            profile_id=profile_id,
            agent_output="No eligibility changes detected under current federal guidelines.",
        )

    # Build narrative prompt
    changed_str = [f"{n}: ${p:,.0f}/mo → ${c:,.0f}/mo" for n, p, c in changed]
    prompt = (
        "You are the AidRadar Monitor Agent running a scheduled re-check triggered by "
        "updated federal poverty guidelines.\n\n"
        "**Eligibility changes (pre-calculated by PolicyEngine — do NOT recalculate):**\n"
        f"- Newly eligible: {', '.join(gained) if gained else 'none'}\n"
        f"- Lost eligibility: {', '.join(lost) if lost else 'none'}\n"
        f"- Benefit amounts changed: {', '.join(changed_str) if changed_str else 'none'}\n\n"
        "Write a short, human-friendly notification (3-5 sentences). "
        "Plain English. Name the programs. Tell the user what to do next."
    )

    agent = create_monitor_agent()
    agent_output = str(agent(prompt))

    return MonitorResult(
        original_income=orig_income,
        new_income=orig_income,
        gained=gained,
        lost=lost,
        changed=changed,
        agent_output=agent_output,
        profile_id=profile_id,
    )
