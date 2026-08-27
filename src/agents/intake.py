"""
Intake Agent — conversational household data collector.

Runs a multi-turn interview to collect 12 fields about the user's household.
Has NO tools — it's purely conversational. The LLM follows the hardened
system prompt to ask one question at a time, handle approximate answers,
and output a structured JSON profile once the user confirms.

The pipeline runner manages the conversation loop: it feeds user input to
this agent repeatedly until the agent outputs a valid JSON profile block.
"""

from functools import lru_cache
from pathlib import Path

from strands import Agent

from src.config import create_mantle_model

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "intake.txt"


@lru_cache(maxsize=None)
def _load_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def create_intake_agent() -> Agent:
    return Agent(model=create_mantle_model(0.3), system_prompt=_load_prompt(), tools=[])
