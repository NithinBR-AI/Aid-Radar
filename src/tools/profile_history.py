"""
Profile History Tool — retrieves the last N eligibility snapshots for a profile.

The Monitor Agent calls this to compare across multiple past snapshots, enabling
trend detection (e.g., benefit gradually declining over 3 checks vs. sudden loss).
This lets the agent distinguish a one-time fluctuation from a sustained change.
"""

from strands import tool

from src.db.profile_store import get_profile


@tool(
    name="get_profile_history",
    description=(
        "Retrieves the eligibility snapshot history for a saved profile. "
        "Returns the current snapshot and up to 2 previous snapshots (oldest first). "
        "Use this to detect trends — a benefit declining across 3 checks is more "
        "significant than a single-check change. Returns empty history if the profile "
        "has only one snapshot on record."
    ),
)
def get_profile_history(profile_id: str) -> dict:
    """Fetch snapshot history for a profile.

    Args:
        profile_id: The UUID of the saved household profile.
    """
    if not profile_id or not isinstance(profile_id, str) or profile_id.lower() == "none":
        return {
            "status": "error",
            "content": [{"text": "profile_id must be a valid non-empty string (not 'None')"}],
        }

    record = get_profile(profile_id)
    if not record:
        return {
            "status": "error",
            "content": [{"text": f"No profile found for profile_id: {profile_id}"}],
        }

    current = record.get("eligibility_snapshot", {})
    history = record.get("snapshot_history", [])

    return {
        "status": "success",
        "content": [
            {
                "json": {
                    "profile_id": profile_id,
                    "current_snapshot": current,
                    "snapshot_history": history,
                    "history_count": len(history),
                }
            }
        ],
    }
