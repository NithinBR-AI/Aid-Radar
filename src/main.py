"""
AidRadar — CLI entry point.

Runs the three-agent pipeline in the terminal:
  1. Intake Agent — collects household profile via multi-turn conversation
  2. Eligibility Agent — evaluates all 8 programs via PolicyEngine
  3. Recommendation Agent — generates plain-language report

Run with: python -m src.main
"""

import json
import re
import sys

from src.agents import (
    create_intake_agent,
    create_eligibility_agent,
    create_recommendation_agent,
)


def _extract_json_profile(text: str) -> dict | None:
    """Extract the first JSON block from agent output."""
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


def _build_eligibility_profile(intake_profile: dict) -> dict:
    """Convert the Intake Agent's profile schema to what eligibility_checker expects."""
    adults = []
    monthly_income = intake_profile.get("monthly_income", 0)
    applicant_age = intake_profile.get("applicant_age", 30)
    adults.append({"age": applicant_age, "income": monthly_income * 12})

    children = []
    for child in intake_profile.get("children_under_5", []) or []:
        children.append({"age": child.get("age", 3)})
    for child in intake_profile.get("children_k12", []) or []:
        children.append({"age": child.get("age", 10)})

    household_size = intake_profile.get("household_size", 1)
    accounted_for = len(adults) + len(children)
    if household_size > accounted_for:
        extra_adults = household_size - accounted_for
        for _ in range(extra_adults):
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


def run_intake() -> dict:
    """Run the Intake Agent conversation loop until a profile is collected."""
    print("\n" + "=" * 60)
    print("  AidRadar — Government Benefit Finder")
    print("=" * 60 + "\n")

    agent = create_intake_agent()

    result = agent("Start the intake interview.")
    agent_text = str(result)
    print(f"\nAidRadar: {agent_text}\n")

    while True:
        user_input = input("You: ").strip()
        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            sys.exit(0)

        result = agent(user_input)
        agent_text = str(result)
        print(f"\nAidRadar: {agent_text}\n")

        profile = _extract_json_profile(agent_text)
        if profile and "state" in profile and "monthly_income" in profile:
            print("\n[Intake complete — profile captured]\n")
            return profile


def run_eligibility(intake_profile: dict) -> str:
    """Run the Eligibility Agent with the collected profile."""
    print("=" * 60)
    print("  Checking eligibility across 8 programs...")
    print("=" * 60 + "\n")

    eligibility_profile = _build_eligibility_profile(intake_profile)

    agent = create_eligibility_agent()

    prompt = (
        "Here is the household profile from the Intake Agent. "
        "Call the eligibility_checker tool with this profile, then call "
        "application_finder for each eligible program. "
        "Output the structured eligibility results.\n\n"
        f"```json\n{json.dumps(eligibility_profile, indent=2)}\n```"
    )

    result = agent(prompt)
    agent_text = str(result)
    print(f"\n{agent_text}\n")
    return agent_text


def run_recommendation(eligibility_results: str, intake_profile: dict) -> str:
    """Run the Recommendation Agent to generate the final report."""
    print("=" * 60)
    print("  Generating your benefits report...")
    print("=" * 60 + "\n")

    agent = create_recommendation_agent()

    prompt = (
        "Here is the household profile and eligibility results. "
        "Generate the full benefits report following your instructions.\n\n"
        f"**Household Profile:**\n```json\n{json.dumps(intake_profile, indent=2)}\n```\n\n"
        f"**Eligibility Results:**\n{eligibility_results}"
    )

    result = agent(prompt)
    agent_text = str(result)
    print(f"\n{agent_text}\n")
    return agent_text


def main():
    """Run the full AidRadar pipeline: Intake → Eligibility → Recommendation."""
    try:
        intake_profile = run_intake()

        print(f"\nCollected profile: {json.dumps(intake_profile, indent=2)}\n")

        eligibility_results = run_eligibility(intake_profile)

        report = run_recommendation(eligibility_results, intake_profile)

        print("\n" + "=" * 60)
        print("  Pipeline complete!")
        print("=" * 60)

    except KeyboardInterrupt:
        print("\n\nInterrupted. Goodbye!")
        sys.exit(0)


if __name__ == "__main__":
    main()
