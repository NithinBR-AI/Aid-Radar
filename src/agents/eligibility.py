"""
Eligibility Agent — PolicyEngine-backed benefit evaluator.

Receives the structured household profile from the Intake Agent and:
1. Calls eligibility_checker to evaluate all 8 programs via PolicyEngine
2. Calls application_finder for each eligible program to get URLs and documents
3. Identifies cascading eligibility chains (SNAP → Free School Meals + Lifeline)
4. Outputs structured eligibility results for the Recommendation Agent

This agent has two tools: eligibility_checker and application_finder.
It does NOT do math — PolicyEngine handles all calculations.
"""

from pathlib import Path

from strands import Agent

from src.config import create_mantle_model
from src.tools.eligibility_checker import eligibility_checker
from src.tools.application_finder import application_finder

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "eligibility.txt"


def _load_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def create_eligibility_agent() -> Agent:
    return Agent(model=create_mantle_model(0.1), system_prompt=_load_prompt(), tools=[eligibility_checker, application_finder])
