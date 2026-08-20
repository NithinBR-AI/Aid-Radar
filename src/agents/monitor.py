"""
Monitor Agent — background eligibility re-checker.

Runs on a schedule (cron/EventBridge). Loads saved household profiles,
re-evaluates eligibility via PolicyEngine, compares against the stored
previous result, and notifies ONLY when something meaningful changed.

Four notification tiers:
  1. Newly eligible for a program (HIGH)
  2. Lost eligibility for a program (HIGH)
  3. Benefit amount changed by >10% (MEDIUM)
  4. Upcoming renewal deadline (MEDIUM)

Uses the same eligibility_checker and application_finder tools as the
Eligibility Agent, plus the hardened monitor prompt to enforce the
"notify only on changes" rule.
"""

from pathlib import Path

from strands import Agent

from src.config import create_mantle_model

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "monitor.txt"


def _load_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def create_monitor_agent() -> Agent:
    # No tools — receives pre-computed diff in prompt, writes narrative only.
    return Agent(model=create_mantle_model(0.1), system_prompt=_load_prompt(), tools=[])
