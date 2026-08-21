"""
Eligibility Agent — interprets pre-computed PolicyEngine results.

The pipeline calls eligibility_checker directly and passes the structured results
in the prompt. This agent has NO tools — it interprets the results, identifies
cascading eligibility chains, and builds a structured summary for the
Recommendation Agent.

application_finder has moved to the Recommendation Agent, which owns the
"how to apply" step and calls it directly for each eligible program.

Separating PolicyEngine (deterministic) from interpretation (LLM) means:
- The programs dict is always authoritative, never parsed from free text
- The agent focuses on what LLMs are good at: reasoning and structuring
"""

from pathlib import Path

from strands import Agent

from src.config import create_mantle_model
from src.tools.application_finder import application_finder

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "eligibility.txt"


def _load_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def create_eligibility_agent() -> Agent:
    return Agent(model=create_mantle_model(0.1), system_prompt=_load_prompt(), tools=[application_finder])
