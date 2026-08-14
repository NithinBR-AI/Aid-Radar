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

import os

from strands import Agent
from strands.models.openai import OpenAIModel

from src.config import MODEL_ID, MANTLE_API_KEY, MANTLE_BASE_URL
from src.tools.eligibility_checker import eligibility_checker
from src.tools.application_finder import application_finder

_PROMPT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")


def _load_prompt() -> str:
    with open(os.path.join(_PROMPT_DIR, "eligibility.txt"), "r", encoding="utf-8") as f:
        return f.read()


def create_eligibility_agent() -> Agent:
    """Create and return a configured Eligibility Agent."""
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
