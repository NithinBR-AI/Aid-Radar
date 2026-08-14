"""
Intake Agent — conversational household data collector.

Runs a multi-turn interview to collect 12 fields about the user's household.
Has NO tools — it's purely conversational. The LLM follows the hardened
system prompt to ask one question at a time, handle approximate answers,
and output a structured JSON profile once the user confirms.

The pipeline runner manages the conversation loop: it feeds user input to
this agent repeatedly until the agent outputs a valid JSON profile block.
"""

import os

from strands import Agent
from strands.models.openai import OpenAIModel

from src.config import MODEL_ID, MANTLE_API_KEY, MANTLE_BASE_URL

_PROMPT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")


def _load_prompt() -> str:
    with open(os.path.join(_PROMPT_DIR, "intake.txt"), "r", encoding="utf-8") as f:
        return f.read()


def create_intake_agent() -> Agent:
    """Create and return a configured Intake Agent."""
    model = OpenAIModel(
        client_args={
            "base_url": MANTLE_BASE_URL,
            "api_key": MANTLE_API_KEY,
            "default_headers": {"openai-project": "default"},
        },
        model_id=MODEL_ID,
        params={"temperature": 0.3},
    )

    return Agent(
        model=model,
        system_prompt=_load_prompt(),
        tools=[],
    )
