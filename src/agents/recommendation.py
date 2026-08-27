"""
Recommendation Agent — plain-language report generator.

Receives the household profile and raw eligibility results (programs dict).
Has one tool: estimate_cliff_effect. For high-value eligible programs where
the household income is near a threshold, the agent calls this tool to check
whether earning $500/month more would cause a benefit cliff. The agent decides
which programs are worth checking — not every program gets a cliff call.

Generates a warm, actionable, 6th-grade reading level report with:
- Summary of eligible programs and total estimated benefit
- Per-program details (amount, how to apply, documents needed)
- Cliff effect warnings where relevant
- Cascading benefit chains
- Next steps prioritized by value
- Disclaimer
"""

from functools import lru_cache
from pathlib import Path

from strands import Agent

from src.config import create_mantle_model
from src.tools.cliff_effect import estimate_cliff_effect

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "recommendation.txt"


@lru_cache(maxsize=None)
def _load_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def create_recommendation_agent() -> Agent:
    return Agent(model=create_mantle_model(0.4), system_prompt=_load_prompt(), tools=[estimate_cliff_effect])
