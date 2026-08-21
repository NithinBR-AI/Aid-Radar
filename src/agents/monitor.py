"""
Monitor Agent — background eligibility re-checker.

Runs on a schedule (cron/EventBridge). Receives the pre-computed diff of
what changed, then uses two tools to build context before writing its narrative:

  1. get_profile_history — fetches the last 3 snapshots so the agent can
     distinguish a one-time fluctuation from a sustained trend.
  2. check_policy_change — checks whether a rule change (not the user's
     situation) caused the eligibility shift. Produces a fundamentally
     different narrative: "policy changed" vs "your situation changed."

Notifies ONLY when something meaningful changed. Zero-change runs produce
zero output.
"""

from pathlib import Path

from strands import Agent

from src.config import create_mantle_model
from src.tools.policy_change import check_policy_change
from src.tools.profile_history import get_profile_history

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "monitor.txt"


def _load_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def create_monitor_agent() -> Agent:
    return Agent(
        model=create_mantle_model(0.1),
        system_prompt=_load_prompt(),
        tools=[get_profile_history, check_policy_change],
    )
