"""
Policy Change Tool — checks the static policy changelog for rule changes.

The Monitor Agent calls this when it detects an eligibility change to determine
whether the change was caused by the user's situation or by a policy update.
These are fundamentally different narratives:
  - "Your income went up and you lost SNAP" → user action needed
  - "Federal SNAP rules changed and you lost SNAP" → informational, not user's fault

Reads from src/data/policy_changelog.json — a curated static file updated
when federal programs publish rule changes. Not real-time; reflects known
changes as of the last data update.
"""

import json
from datetime import date
from pathlib import Path

from strands import tool

_CHANGELOG_PATH = Path(__file__).parent.parent / "data" / "policy_changelog.json"


def _load_changelog() -> dict:
    try:
        return json.loads(_CHANGELOG_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        raise RuntimeError(f"policy_changelog.json could not be loaded: {e}") from e


@tool(
    name="check_policy_change",
    description=(
        "Checks whether a federal benefit program had a known policy or rule change "
        "after a given date. Returns matching changelog entries for the program and state. "
        "Use this when you detect an eligibility change to determine whether it was caused "
        "by a policy update (not the user's situation changing). Returns an empty list if "
        "no policy changes are found for that program after the given date."
    ),
)
def check_policy_change(
    program_id: str,
    state: str,
    since_date: str,
) -> dict:
    """Check for policy changes for a program since a given date.

    Args:
        program_id: Program identifier (e.g., 'snap', 'medicaid', 'wic').
        state: Two-letter state code (e.g., 'CA') or 'ALL' for federal-level changes.
        since_date: ISO date string (YYYY-MM-DD). Returns changes on or after this date.
    """
    try:
        changelog = _load_changelog()
    except RuntimeError as e:
        return {
            "status": "error",
            "content": [{"text": str(e)}],
        }

    program_id = program_id.lower()
    state = state.upper()

    try:
        since = date.fromisoformat(since_date)
    except ValueError:
        return {
            "status": "error",
            "content": [{"text": f"since_date must be ISO format YYYY-MM-DD, got: {since_date!r}"}],
        }

    entries = changelog.get(program_id)
    if entries is None:
        return {
            "status": "error",
            "content": [{"text": f"Unknown program_id: {program_id}. Check spelling."}],
        }

    matching = [
        e for e in entries
        if date.fromisoformat(e["date"]) >= since
        and (state in e.get("states", []) or "ALL" in e.get("states", []))
    ]

    return {
        "status": "success",
        "content": [
            {
                "json": {
                    "program_id": program_id,
                    "state": state,
                    "since_date": since_date,
                    "changes_found": len(matching),
                    "changes": matching,
                    "policy_driven": len(matching) > 0,
                }
            }
        ],
    }
