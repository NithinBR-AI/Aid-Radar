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

import os

from strands import Agent
from strands.models.openai import OpenAIModel

from src.config import MODEL_ID, MANTLE_API_KEY, MANTLE_BASE_URL
from src.tools.eligibility_checker import eligibility_checker
from src.tools.application_finder import application_finder

_PROMPT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")


def _load_prompt() -> str:
    with open(os.path.join(_PROMPT_DIR, "monitor.txt"), "r", encoding="utf-8") as f:
        return f.read()


def create_monitor_agent() -> Agent:
    """Create and return a configured Monitor Agent."""
    model = OpenAIModel(
        client_args={
            "base_url": MANTLE_BASE_URL,
            "api_key": MANTLE_API_KEY,
            "default_headers": {"openai-project": "default"},
        },
        model_id=MODEL_ID,
        params={"temperature": 0.1},
    )

    return Agent(
        model=model,
        system_prompt=_load_prompt(),
        tools=[eligibility_checker, application_finder],
    )
