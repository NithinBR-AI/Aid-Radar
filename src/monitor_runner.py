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
from datetime import datetime, timezone

from src.config import get_boto_session
from src.pipeline.monitor_pipeline import run_monitor_check

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

    for item in items:
        profile_id = item["profile_id"]
        # boto3 returns DynamoDB Map types as Python dicts — not JSON strings
        profile = item["profile"] if isinstance(item["profile"], dict) else json.loads(item["profile"])
        previous_snapshot = item["eligibility_snapshot"] if isinstance(item["eligibility_snapshot"], dict) else json.loads(item["eligibility_snapshot"])

        print(f"--- Checking profile: {profile_id[:8]}... (state={item.get('state')}) ---")

        result = run_monitor_check(profile_id, profile, previous_snapshot)

        if result.error:
            print(f"  Error: {result.error}\n")
            continue

        if not result.has_changes:
            print(f"  No eligibility changes — skipping notification.\n")
            continue

        if result.gained:
            print(f"  Newly eligible: {', '.join(result.gained)}")
        if result.lost:
            print(f"  Lost eligibility: {', '.join(result.lost)}")
        if result.changed:
            for name, prev, curr in result.changed:
                print(f"  Changed: {name} ${prev:,.0f}/mo → ${curr:,.0f}/mo")

        print(f"\n{result.agent_output}\n")
        print(f"  Snapshot updated in DynamoDB.\n")

    print(f"{'=' * 60}")
    print("  Monitor run complete.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    run_monitor()
