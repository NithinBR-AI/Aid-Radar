"""
Recommendation Agent — plain-language report generator.

Receives eligibility results from the Eligibility Agent and the original
household profile. Generates a warm, actionable, 6th-grade reading level
report with:
- Summary of eligible programs and total estimated benefit
- Per-program details (amount, how to apply, documents needed)
- Cascading benefit chains
- Next steps prioritized by value
- Disclaimer

Has NO tools — it's purely a language generation agent. All data comes
from the eligibility results passed in the prompt.
"""

from pathlib import Path

from strands import Agent

from src.config import create_mantle_model

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "recommendation.txt"


def _load_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def create_recommendation_agent() -> Agent:
    return Agent(model=create_mantle_model(0.4), system_prompt=_load_prompt(), tools=[])
