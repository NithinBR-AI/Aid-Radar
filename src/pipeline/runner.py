"""
AidRadar Pipeline Runner — agent orchestration, decoupled from Streamlit UI.

Owns:
  - Profile extraction from agent text
  - Intake → Eligibility → Recommendation pipeline
  - What If eligibility re-calculation
  - Eligibility profile format conversion

The Streamlit app calls these functions; it never orchestrates agents directly.
"""

import copy
import json
import re
from dataclasses import dataclass, field

from src.agents import create_eligibility_agent, create_recommendation_agent
from src.db.profile_store import save_profile
from src.tools.eligibility_checker import eligibility_checker


@dataclass
class PipelineResult:
    eligibility_text: str
    report_text: str
    programs: dict = field(default_factory=dict)
    profile_id: str | None = None
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None


def extract_json_profile(text: str) -> dict | None:
    """Extract the first JSON object from agent output."""
    pattern = r"```(?:json)?\s*(\{.*?\})\s*```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
    try:
        brace_start = text.index("{")
        brace_end = text.rindex("}") + 1
        return json.loads(text[brace_start:brace_end])
    except (ValueError, json.JSONDecodeError):
        return None


def build_eligibility_profile(intake_profile: dict) -> dict:
    """Convert the Intake Agent's profile schema to what eligibility_checker expects."""
    monthly_income = intake_profile.get("monthly_income", 0)
    applicant_age = intake_profile.get("applicant_age", 30)
    adults = [{"age": applicant_age, "income": monthly_income * 12}]

    children = []
    for child in intake_profile.get("children_under_5", []) or []:
        children.append({"age": child.get("age", 3)})
    for child in intake_profile.get("children_k12", []) or []:
        children.append({"age": child.get("age", 10)})

    household_size = intake_profile.get("household_size", 1)
    accounted_for = len(adults) + len(children)
    if household_size > accounted_for:
        for _ in range(household_size - accounted_for):
            adults.append({"age": 30, "income": 0})

    return {
        "state": intake_profile.get("state", "CA"),
        "monthly_income": monthly_income,
        "adults": adults,
        "children": children,
        "has_disabled_member": intake_profile.get("has_disabled_member", False),
        "has_pregnant_member": intake_profile.get("has_pregnant_member", False),
        "has_elderly_65_plus": intake_profile.get("has_elderly_65_plus", False),
        "current_programs": intake_profile.get("current_programs", []),
        "veteran_in_household": intake_profile.get("veteran_in_household", False),
        "citizenship_status": intake_profile.get("citizenship_status"),
        "income_is_approximate": intake_profile.get("income_is_approximate", False),
    }


def run_pipeline(intake_profile: dict) -> PipelineResult:
    """
    Run Eligibility Agent → direct PolicyEngine check → Recommendation Agent.

    The Eligibility Agent produces structured text for the Recommendation Agent.
    The direct check (same profile, same moment) captures raw program data for
    the What If baseline and DynamoDB — no second PolicyEngine invocation, no drift.
    """
    eligibility_profile = build_eligibility_profile(intake_profile)

    # Step 1: Eligibility Agent (LLM + tool calls → structured text)
    agent = create_eligibility_agent()
    prompt = (
        "Here is the household profile from the Intake Agent. "
        "Call the eligibility_checker tool with this profile, then call "
        "application_finder for each eligible program. "
        "Output the structured eligibility results.\n\n"
        f"```json\n{json.dumps(eligibility_profile, indent=2)}\n```"
    )
    eligibility_text = str(agent(prompt))

    # Step 2: Direct tool call for raw program data (baseline + DynamoDB)
    # Uses the same profile as the agent — single source of truth, no re-computation.
    programs: dict = {}
    profile_id: str | None = None
    raw = eligibility_checker(json.dumps(eligibility_profile))
    if raw.get("status") == "success":
        programs = raw["content"][0]["json"]["programs"]
        try:
            profile_id = save_profile(intake_profile, programs)
        except Exception:
            profile_id = None

    # Step 3: Recommendation Agent
    rec_agent = create_recommendation_agent()
    rec_prompt = (
        "Here is the household profile and eligibility results. "
        "Generate the full benefits report following your instructions.\n\n"
        f"**Household Profile:**\n```json\n{json.dumps(intake_profile, indent=2)}\n```\n\n"
        f"**Eligibility Results:**\n{eligibility_text}"
    )
    report_text = str(rec_agent(rec_prompt))

    return PipelineResult(
        eligibility_text=eligibility_text,
        report_text=report_text,
        programs=programs,
        profile_id=profile_id,
    )


def run_whatif(base_profile: dict, monthly_income: int, num_adults: int, num_children: int) -> dict:
    """Re-run eligibility_checker for a modified household. Returns programs dict."""
    p = copy.deepcopy(base_profile)
    p["monthly_income"] = monthly_income

    annual = monthly_income * 12
    existing_adults = p.get("adults", [])
    p["adults"] = [
        {"age": existing_adults[i]["age"] if i < len(existing_adults) else 35,
         "income": annual if i == 0 else 0}
        for i in range(num_adults)
    ]

    existing_children = p.get("children", [])
    p["children"] = [
        {"age": existing_children[i]["age"] if i < len(existing_children) else 5}
        for i in range(num_children)
    ]

    result = eligibility_checker(json.dumps(p))
    if result.get("status") != "success":
        return {}
    return result["content"][0]["json"]["programs"]
