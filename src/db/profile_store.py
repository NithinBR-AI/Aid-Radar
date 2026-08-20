"""
Profile Store — DynamoDB-backed persistence for AidRadar household profiles.

Stores profile + eligibility snapshot so the Monitor Agent can:
  1. Load saved profiles on a schedule
  2. Re-run eligibility_checker against the current rules
  3. Diff new results against the stored snapshot
  4. Notify only on real changes

Table: aid-radar-profiles
PK: profile_id (UUID string)
TTL: 90 days from last update (no PII sitting indefinitely)
"""

import json
import uuid
from datetime import datetime, timezone, timedelta

from botocore.exceptions import ClientError

from src.config import get_boto_session
from src.guardrails.profile_validator import safe_serialize

_TABLE_NAME = "aid-radar-profiles"
_TTL_DAYS = 90


def _table():
    dynamodb = get_boto_session().resource("dynamodb")
    return dynamodb.Table(_TABLE_NAME)


def ensure_table_exists() -> None:
    """Create the DynamoDB table if it doesn't exist. Idempotent."""
    client = get_boto_session().client("dynamodb")
    try:
        client.describe_table(TableName=_TABLE_NAME)
    except client.exceptions.ResourceNotFoundException:
        client.create_table(
            TableName=_TABLE_NAME,
            KeySchema=[{"AttributeName": "profile_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "profile_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        waiter = client.get_waiter("table_exists")
        waiter.wait(TableName=_TABLE_NAME)
        client.update_time_to_live(
            TableName=_TABLE_NAME,
            TimeToLiveSpecification={"Enabled": True, "AttributeName": "ttl"},
        )


def save_profile(profile: dict, eligibility_snapshot: dict) -> str:
    """Save a new profile + eligibility snapshot. Returns profile_id."""
    ensure_table_exists()

    profile_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    ttl = int((now + timedelta(days=_TTL_DAYS)).timestamp())

    _table().put_item(Item={
        "profile_id": profile_id,
        "profile": json.dumps(profile, default=safe_serialize),
        "eligibility_snapshot": json.dumps(eligibility_snapshot, default=safe_serialize),
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "state": profile.get("state", "unknown").upper(),
        "ttl": ttl,
    })

    return profile_id


def get_profile(profile_id: str) -> dict | None:
    """Load a saved profile by ID. Returns None if not found."""
    try:
        response = _table().get_item(Key={"profile_id": profile_id})
        item = response.get("Item")
        if not item:
            return None
        return {
            "profile_id": item["profile_id"],
            "profile": json.loads(item["profile"]),
            "eligibility_snapshot": json.loads(item["eligibility_snapshot"]),
            "created_at": item["created_at"],
            "updated_at": item["updated_at"],
            "state": item["state"],
        }
    except ClientError:
        return None


def update_snapshot(profile_id: str, new_snapshot: dict) -> bool:
    """Update the eligibility snapshot after a Monitor Agent re-check."""
    try:
        now = datetime.now(timezone.utc)
        ttl = int((now + timedelta(days=_TTL_DAYS)).timestamp())
        _table().update_item(
            Key={"profile_id": profile_id},
            UpdateExpression="SET eligibility_snapshot = :s, updated_at = :u, #t = :ttl",
            ExpressionAttributeNames={"#t": "ttl"},
            ExpressionAttributeValues={
                ":s": json.dumps(new_snapshot, default=safe_serialize),
                ":u": now.isoformat(),
                ":ttl": ttl,
            },
        )
        return True
    except ClientError:
        return False
