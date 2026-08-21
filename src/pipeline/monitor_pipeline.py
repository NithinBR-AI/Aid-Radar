"""
Monitor Pipeline — eligibility re-check and diff logic.

Decoupled from Streamlit. Called by app.py (UI wrapper) and monitor_runner.py (cron).
"""

import json
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

from src.agents import create_monitor_agent
from src.db.profile_store import get_profile, update_snapshot
from src.pipeline.runner import build_eligibility_profile

_MONITOR_AGENT_TIMEOUT_SECONDS = 120
from src.tools.eligibility_checker import eligibility_checker

logger = logging.getLogger(__name__)

# Changes below this threshold ($/month) are treated as rounding noise, not real changes.
# SNAP and most programs adjust by small cents-level amounts when FPL changes slightly.
# $5/month was chosen to avoid alerting users about sub-meaningful fluctuations.
_BENEFIT_CHANGE_THRESHOLD = 5


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
            prev_amt = float((prev.get("estimated_benefit") or {}).get("monthly", 0) or 0)
            curr_amt = float((curr.get("estimated_benefit") or {}).get("monthly", 0) or 0)
            if abs(curr_amt - prev_amt) > _BENEFIT_CHANGE_THRESHOLD:
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
    if not isinstance(intake_profile, dict) or not intake_profile.get("state"):
        return MonitorResult(
            original_income=0,
            new_income=0,
            error="Invalid intake profile passed to monitor check.",
        )

    orig_income = int(intake_profile.get("monthly_income") or 0)

    # Load from DynamoDB; fall back to in-session baseline if not found
    saved = get_profile(profile_id) if profile_id else None
    previous_snapshot = saved["eligibility_snapshot"] if saved else baseline_programs

    # Re-run eligibility at the same income — any differences are rule changes.
    # build_eligibility_profile() converts the intake schema to eligibility_checker's
    # expected schema. validate_profile() runs inside eligibility_checker.
    try:
        eligibility_profile = build_eligibility_profile(intake_profile)
    except ValueError as e:
        return MonitorResult(
            original_income=orig_income,
            new_income=orig_income,
            error=f"Profile schema error: {e}",
        )

    raw = eligibility_checker(json.dumps(eligibility_profile))
    if raw.get("status") != "success":
        logger.error("monitor_check eligibility_checker failed profile_id=%s", profile_id)
        return MonitorResult(
            original_income=orig_income,
            new_income=orig_income,
            error="Eligibility check failed",
        )

    new_snapshot = raw["content"][0]["json"]["programs"]

    if profile_id:
        # Pass already-loaded snapshot data to avoid a redundant DynamoDB read in update_snapshot
        update_snapshot(
            profile_id,
            new_snapshot,
            current_snapshot=saved["eligibility_snapshot"] if saved else None,
            current_history=saved.get("snapshot_history", []) if saved else None,
        )

    gained, lost, changed = _diff_snapshots(previous_snapshot, new_snapshot)
    logger.info(
        "monitor_check diff profile_id=%s gained=%s lost=%s changed=%d",
        profile_id, gained, lost, len(changed),
    )

    if not gained and not lost and not changed:
        logger.info("monitor_check no_changes profile_id=%s", profile_id)
        return MonitorResult(
            original_income=orig_income,
            new_income=orig_income,
            profile_id=profile_id,
            agent_output="No eligibility changes detected under current federal guidelines.",
        )

    # Build narrative prompt — include profile_id so agent can call get_profile_history,
    # state and snapshot date so it can call check_policy_change with correct context.
    changed_str = [f"{n}: ${p:,.0f}/mo → ${c:,.0f}/mo" for n, p, c in changed]
    state = intake_profile.get("state", "unknown").upper()
    # Fall back to 90 days ago rather than a hardcoded 2024 date — avoids flooding
    # check_policy_change with 2+ years of policy history on first run.
    _ninety_days_ago = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%d")
    snapshot_date = (saved or {}).get("updated_at", _ninety_days_ago)[:10]  # ISO date only

    history_instruction = (
        f"Call get_profile_history(profile_id='{profile_id}') to check for trends, "
        "then " if profile_id else ""
    )

    prompt = (
        "You are the AidRadar Monitor Agent running a scheduled re-check.\n\n"
        + (f"**Profile ID:** {profile_id}\n" if profile_id else "**Profile ID:** not available — skip get_profile_history\n")
        + f"**State:** {state}\n"
        f"**Previous snapshot date:** {snapshot_date}\n\n"
        "**Eligibility changes (pre-calculated by PolicyEngine — do NOT recalculate):**\n"
        f"- Newly eligible: {', '.join(gained) if gained else 'none'}\n"
        f"- Lost eligibility: {', '.join(lost) if lost else 'none'}\n"
        f"- Benefit amounts changed: {', '.join(changed_str) if changed_str else 'none'}\n\n"
        f"Follow your instructions: {history_instruction}call check_policy_change for "
        "each changed program, then write the narrative. Plain English. 3-5 sentences."
    )

    agent = create_monitor_agent()
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(agent, prompt)
            agent_output = str(future.result(timeout=_MONITOR_AGENT_TIMEOUT_SECONDS))
    except FuturesTimeoutError:
        logger.error("monitor_check agent_timeout exceeded=%ds profile_id=%s", _MONITOR_AGENT_TIMEOUT_SECONDS, profile_id)
        agent_output = "Eligibility changes were detected but the notification could not be generated — will retry on the next scheduled check."

    return MonitorResult(
        original_income=orig_income,
        new_income=orig_income,
        gained=gained,
        lost=lost,
        changed=changed,
        agent_output=agent_output,
        profile_id=profile_id,
    )
