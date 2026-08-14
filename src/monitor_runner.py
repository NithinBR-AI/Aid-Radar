"""
AidRadar — Monitor Agent standalone runner.
Run with: python -m src.monitor_runner

This script runs independently of the web app. It:
- Loads all saved user profiles from local storage (DynamoDB in production)
- Re-checks eligibility against current program thresholds via PolicyEngine
- Compares results to previous eligibility snapshots
- Sends notifications only when something changed

Intended to be triggered by:
- AWS EventBridge Scheduler (production)
- Manual invocation for demo: python -m src.monitor_runner --run-now
- Strands cron tool within a long-running agent process
"""

import json
import os
import sys
from datetime import datetime

from src.agents import create_monitor_agent

_PROFILES_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "profiles")
_SNAPSHOTS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "snapshots")


def _ensure_dirs():
    os.makedirs(_PROFILES_DIR, exist_ok=True)
    os.makedirs(_SNAPSHOTS_DIR, exist_ok=True)


def _load_profiles() -> list[dict]:
    """Load all saved household profiles."""
    profiles = []
    if not os.path.exists(_PROFILES_DIR):
        return profiles
    for fname in os.listdir(_PROFILES_DIR):
        if fname.endswith(".json"):
            with open(os.path.join(_PROFILES_DIR, fname), "r", encoding="utf-8") as f:
                profile = json.load(f)
                profile["_profile_id"] = fname.replace(".json", "")
                profiles.append(profile)
    return profiles


def _load_previous_snapshot(profile_id: str) -> dict | None:
    """Load the most recent eligibility snapshot for a profile."""
    path = os.path.join(_SNAPSHOTS_DIR, f"{profile_id}_latest.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _save_snapshot(profile_id: str, snapshot: dict):
    """Save the current eligibility snapshot."""
    path = os.path.join(_SNAPSHOTS_DIR, f"{profile_id}_latest.json")
    snapshot["_timestamp"] = datetime.utcnow().isoformat()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)


def run_monitor():
    """Run the Monitor Agent for all saved profiles."""
    _ensure_dirs()
    profiles = _load_profiles()

    if not profiles:
        print("No saved profiles found. Run the main pipeline first to create a profile.")
        return

    print(f"\n{'=' * 60}")
    print(f"  AidRadar Monitor — checking {len(profiles)} profile(s)")
    print(f"  {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'=' * 60}\n")

    agent = create_monitor_agent()

    for profile in profiles:
        profile_id = profile.pop("_profile_id")
        previous = _load_previous_snapshot(profile_id)

        prompt = (
            f"Check this profile for eligibility changes.\n\n"
            f"**Profile (ID: {profile_id}):**\n"
            f"```json\n{json.dumps(profile, indent=2)}\n```\n\n"
        )

        if previous:
            prompt += (
                f"**Previous eligibility snapshot:**\n"
                f"```json\n{json.dumps(previous, indent=2)}\n```\n\n"
                "Compare the current eligibility (call eligibility_checker) "
                "against the previous snapshot. Only report meaningful changes."
            )
        else:
            prompt += (
                "No previous snapshot exists — this is the first run for this profile. "
                "Call eligibility_checker to establish the baseline. "
                "Do NOT send any notifications on the first run."
            )

        print(f"--- Checking profile: {profile_id} ---")
        result = agent(prompt)
        agent_text = str(result)
        print(f"\n{agent_text}\n")

    print(f"\n{'=' * 60}")
    print("  Monitor run complete.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    run_monitor()
