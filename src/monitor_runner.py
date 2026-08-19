"""
AidRadar Monitor Runner — DynamoDB-backed scheduled eligibility re-checker.

Intended to be triggered by AWS EventBridge on a cron schedule.
Can also be run manually: python -m src.monitor_runner

For each saved profile in DynamoDB:
  1. Load profile + previous eligibility snapshot
  2. Re-run eligibility_checker (PolicyEngine) with current rules
  3. Diff new vs stored snapshot
  4. Log changes (extend to notify via SNS/email in production)
  5. Update snapshot in DynamoDB
"""

import json
import sys
from datetime import datetime, timezone

from src.agents import create_monitor_agent
from src.config import get_boto_session
from src.tools.eligibility_checker import eligibility_checker
from src.tools.profile_store import update_snapshot

_TABLE_NAME = "aid-radar-profiles"


def _scan_all_profiles() -> list[dict]:
    """Scan all profiles from DynamoDB."""
    dynamodb = get_boto_session().resource("dynamodb")
    table = dynamodb.Table(_TABLE_NAME)
    try:
        response = table.scan()
        return response.get("Items", [])
    except Exception as e:
        print(f"Failed to scan DynamoDB: {e}")
        return []


def run_monitor():
    """Run Monitor Agent for all saved profiles."""
    items = _scan_all_profiles()

    if not items:
        print("No saved profiles in DynamoDB. Run the Streamlit app to create profiles.")
        return

    print(f"\n{'=' * 60}")
    print(f"  AidRadar Monitor — {len(items)} profile(s)")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'=' * 60}\n")

    agent = create_monitor_agent()

    for item in items:
        profile_id = item["profile_id"]
        profile = json.loads(item["profile"])
        previous_snapshot = json.loads(item["eligibility_snapshot"])

        print(f"--- Checking profile: {profile_id[:8]}... (state={item.get('state')}) ---")

        # Re-run real eligibility check
        raw = eligibility_checker(json.dumps(profile))
        if raw.get("status") != "success":
            print(f"  Eligibility check failed — skipping")
            continue

        new_snapshot = raw["content"][0]["json"]["programs"]

        # Pre-compute diff so the agent focuses on narrative, not recalculation
        gained = [
            new_snapshot[pid].get("display_name") or pid
            for pid in new_snapshot
            if new_snapshot[pid].get("eligible") and not previous_snapshot.get(pid, {}).get("eligible")
        ]
        lost = [
            previous_snapshot[pid].get("display_name") or pid
            for pid in previous_snapshot
            if previous_snapshot[pid].get("eligible") and not new_snapshot.get(pid, {}).get("eligible")
        ]

        if not gained and not lost:
            print(f"  No eligibility changes — skipping notification.\n")
            update_snapshot(profile_id, new_snapshot)
            continue

        prompt = (
            f"Scheduled re-check for profile {profile_id[:8]} (state={item.get('state')}).\n\n"
            "**Eligibility changes (already calculated — do NOT recalculate):**\n"
            f"- Newly eligible: {', '.join(gained) if gained else 'none'}\n"
            f"- Lost eligibility: {', '.join(lost) if lost else 'none'}\n\n"
            "Write a short notification (2-3 sentences) the user would receive via email or SMS. "
            "Plain English. Name the programs. Tell them what to do next."
        )

        result = agent(prompt)
        print(f"\n{result}\n")

        update_snapshot(profile_id, new_snapshot)
        print(f"  Snapshot updated in DynamoDB.\n")

    print(f"{'=' * 60}")
    print("  Monitor run complete.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    run_monitor()
