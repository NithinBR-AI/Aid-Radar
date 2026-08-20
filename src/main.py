"""
AidRadar — CLI entry point.

Runs the three-agent pipeline in the terminal:
  1. Intake Agent — collects household profile via multi-turn conversation
  2. Eligibility Agent — evaluates all 8 programs via PolicyEngine
  3. Recommendation Agent — generates plain-language report

Run with: python -m src.main
"""

import json
import sys

from src.agents import create_intake_agent
from src.pipeline.runner import extract_json_profile, run_pipeline


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

        profile = extract_json_profile(agent_text)
        if profile and "state" in profile and "monthly_income" in profile:
            print("\n[Intake complete — profile captured]\n")
            return profile


def main():
    """Run the full AidRadar pipeline: Intake → Eligibility → Recommendation."""
    try:
        intake_profile = run_intake()
        print(f"\nCollected profile: {json.dumps(intake_profile, indent=2)}\n")

        print("=" * 60)
        print("  Checking eligibility across 8 programs...")
        print("=" * 60 + "\n")
        result = run_pipeline(intake_profile)

        print(result.eligibility_text)
        print("\n" + "=" * 60)
        print("  Generating your benefits report...")
        print("=" * 60 + "\n")
        print(result.report_text)

        print("\n" + "=" * 60)
        print("  Pipeline complete!")
        print("=" * 60)

    except KeyboardInterrupt:
        print("\n\nInterrupted. Goodbye!")
        sys.exit(0)


if __name__ == "__main__":
    main()
