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
import logging
import uuid
from decimal import Decimal
from datetime import datetime, timezone, timedelta

from botocore.exceptions import ClientError

from src.config import get_boto_session
from src.guardrails.profile_validator import safe_serialize

logger = logging.getLogger(__name__)

_TABLE_NAME = "aid-radar-profiles"


def _to_dynamo(obj):
    """Recursively convert floats to Decimal for DynamoDB native map storage.

    boto3 rejects Python float values in native maps — Decimal is required.
    We round-trip through JSON first to normalise numpy/non-standard types,
    then walk the result converting every float.
    """
    if isinstance(obj, dict):
        return {k: _to_dynamo(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_dynamo(i) for i in obj]
    if isinstance(obj, float):
        return Decimal(str(obj))
    return obj
_TTL_DAYS = 90
_table_ensured = False  # module-level flag — avoid repeated describe_table on every write


def _table():
    dynamodb = get_boto_session().resource("dynamodb")
    return dynamodb.Table(_TABLE_NAME)


def ensure_table_exists() -> None:
    """Create the DynamoDB table if it doesn't exist. Idempotent. Only runs once per process."""
    global _table_ensured
    if _table_ensured:
        return
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
    _table_ensured = True


def save_profile(profile: dict, eligibility_snapshot: dict) -> str:
    """Save a new profile + eligibility snapshot. Returns profile_id."""
    ensure_table_exists()

    profile_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    ttl = int((now + timedelta(days=_TTL_DAYS)).timestamp())

    # Store as native DynamoDB maps (not JSON strings) so fields are queryable.
    # json round-trip normalises numpy types; _to_dynamo converts floats → Decimal
    # (boto3 rejects Python floats in native maps).
    clean_profile = _to_dynamo(json.loads(json.dumps(profile, default=safe_serialize)))
    clean_snapshot = _to_dynamo(json.loads(json.dumps(eligibility_snapshot, default=safe_serialize)))

    _table().put_item(Item={
        "profile_id": profile_id,
        "profile": clean_profile,
        "eligibility_snapshot": clean_snapshot,
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
            "profile": item["profile"],
            "eligibility_snapshot": item["eligibility_snapshot"],
            "snapshot_history": item.get("snapshot_history", []),
            "created_at": item["created_at"],
            "updated_at": item["updated_at"],
            "state": item["state"],
        }
    except ClientError as e:
        logger.error("get_profile failed profile_id=%s error=%s", profile_id, e.response["Error"]["Code"])
        return None


_SNAPSHOT_HISTORY_MAX = 3  # keep last N snapshots for trend detection by Monitor Agent


def update_snapshot(
    profile_id: str,
    new_snapshot: dict,
    current_snapshot: dict | None = None,
    current_history: list | None = None,
) -> bool:
    """Update the eligibility snapshot after a Monitor Agent re-check.

    Appends the current snapshot to snapshot_history (capped at _SNAPSHOT_HISTORY_MAX)
    before overwriting eligibility_snapshot with the new result. This lets the
    Monitor Agent call get_profile_history to compare across multiple past checks.

    Pass current_snapshot and current_history if already loaded to avoid a redundant
    DynamoDB read. If omitted, the record is fetched from DynamoDB.
    """
    if current_snapshot is None or current_history is None:
        record = get_profile(profile_id)
        if not record:
            logger.error("update_snapshot profile_not_found profile_id=%s", profile_id)
            return False
        current_snapshot = current_snapshot or record.get("eligibility_snapshot", {})
        current_history = current_history if current_history is not None else record.get("snapshot_history", [])

    # Append current snapshot to history before overwriting
    history = list(current_history) if isinstance(current_history, list) else []
    if current_snapshot:
        history.append(current_snapshot)
    history = history[-_SNAPSHOT_HISTORY_MAX:]  # keep only the last N

    try:
        now = datetime.now(timezone.utc)
        ttl = int((now + timedelta(days=_TTL_DAYS)).timestamp())
        clean_snapshot = _to_dynamo(json.loads(json.dumps(new_snapshot, default=safe_serialize)))
        clean_history = _to_dynamo(history)
        _table().update_item(
            Key={"profile_id": profile_id},
            UpdateExpression=(
                "SET eligibility_snapshot = :s, snapshot_history = :h, "
                "updated_at = :u, #t = :ttl"
            ),
            ExpressionAttributeNames={"#t": "ttl"},
            ExpressionAttributeValues={
                ":s": clean_snapshot,
                ":h": clean_history,
                ":u": now.isoformat(),
                ":ttl": ttl,
            },
        )
        return True
    except ClientError as e:
        logger.error("update_snapshot failed profile_id=%s error=%s", profile_id, e.response["Error"]["Code"])
        return False
