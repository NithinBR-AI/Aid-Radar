"""
Integration tests — hit real DynamoDB.
Requires AWS credentials. Skipped automatically if unavailable.
Run with: pytest tests/integration/test_profile_store_integration.py -v
"""
import pytest
import boto3
from botocore.exceptions import NoCredentialsError, EndpointResolutionError

from src.db.profile_store import save_profile, get_profile, update_snapshot


def _has_aws_credentials():
    try:
        boto3.Session().client("sts").get_caller_identity()
        return True
    except Exception:
        return False


needs_aws = pytest.mark.skipif(
    not _has_aws_credentials(),
    reason="AWS credentials not available",
)

SAMPLE_PROFILE = {
    "state": "CA",
    "monthly_income": 2000,
    "household_size": 3,
    "applicant_age": 32,
}

SAMPLE_SNAPSHOT = {
    "snap": {"eligible": True, "estimated_benefit": {"monthly": 300.0}},
    "medicaid": {"eligible": True, "estimated_benefit": None},
}


@needs_aws
def test_save_profile_returns_id():
    profile_id = save_profile(SAMPLE_PROFILE, SAMPLE_SNAPSHOT)
    assert isinstance(profile_id, str)
    assert len(profile_id) > 0


@needs_aws
def test_get_profile_returns_saved_data():
    profile_id = save_profile(SAMPLE_PROFILE, SAMPLE_SNAPSHOT)
    saved = get_profile(profile_id)
    assert saved is not None
    assert saved["profile"]["state"] == "CA"


@needs_aws
def test_get_profile_includes_snapshot():
    profile_id = save_profile(SAMPLE_PROFILE, SAMPLE_SNAPSHOT)
    saved = get_profile(profile_id)
    assert "eligibility_snapshot" in saved
    assert "snap" in saved["eligibility_snapshot"]


@needs_aws
def test_update_snapshot_overwrites():
    profile_id = save_profile(SAMPLE_PROFILE, SAMPLE_SNAPSHOT)
    new_snapshot = {**SAMPLE_SNAPSHOT, "snap": {"eligible": False}}
    update_snapshot(profile_id, new_snapshot)
    saved = get_profile(profile_id)
    assert saved["eligibility_snapshot"]["snap"]["eligible"] is False


@needs_aws
def test_get_nonexistent_profile_returns_none():
    result = get_profile("nonexistent-profile-id-xyz-123")
    assert result is None


@needs_aws
def test_update_snapshot_appends_to_history():
    profile_id = save_profile(SAMPLE_PROFILE, SAMPLE_SNAPSHOT)
    new_snapshot = {**SAMPLE_SNAPSHOT, "snap": {"eligible": False, "estimated_benefit": None}}
    update_snapshot(profile_id, new_snapshot)
    saved = get_profile(profile_id)
    # History should contain the original snapshot
    assert len(saved["snapshot_history"]) == 1
    assert "snap" in saved["snapshot_history"][0]


@needs_aws
def test_update_snapshot_caps_history_at_3():
    profile_id = save_profile(SAMPLE_PROFILE, SAMPLE_SNAPSHOT)
    # Run 4 updates — history should cap at 3
    for i in range(4):
        snap = {**SAMPLE_SNAPSHOT, "snap": {"eligible": True, "estimated_benefit": {"monthly": float(200 + i * 10)}}}
        update_snapshot(profile_id, snap)
    saved = get_profile(profile_id)
    assert len(saved["snapshot_history"]) <= 3


@needs_aws
def test_get_profile_returns_snapshot_history_key():
    profile_id = save_profile(SAMPLE_PROFILE, SAMPLE_SNAPSHOT)
    saved = get_profile(profile_id)
    assert "snapshot_history" in saved
    assert isinstance(saved["snapshot_history"], list)
