"""
AidRadar Agent Definitions.

Three-agent pipeline for benefit eligibility evaluation:

    IntakeAgent         — Conversational interview to collect household profile
    EligibilityAgent    — PolicyEngine-backed eligibility check across all programs
    RecommendationAgent — Plain-language report with actionable next steps

Each agent is a factory function that returns a configured Strands Agent
instance with the appropriate system prompt, tools, and model.
"""

from src.agents.intake import create_intake_agent
from src.agents.eligibility import create_eligibility_agent
from src.agents.recommendation import create_recommendation_agent
from src.agents.monitor import create_monitor_agent

__all__ = [
    "create_intake_agent",
    "create_eligibility_agent",
    "create_recommendation_agent",
    "create_monitor_agent",
]
