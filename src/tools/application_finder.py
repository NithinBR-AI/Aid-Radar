"""
Application Finder Tool.

Retrieves the correct application URL, required documents, and application
process notes for a specific benefit program in a specific state.

This tool exists because application processes vary significantly by state:
- SNAP in California uses BenefitsCal.com
- SNAP in Texas uses YourTexasBenefits.com
- Some programs have a universal federal application (Lifeline → nv.fcc.gov)
- Some programs apply through local offices (WIC, SSI)

The tool reads ONLY from the program JSON data files. It never generates,
guesses, or constructs URLs. If no state-specific URL exists, it falls back
to the federal URL and notes that the user should search for their state's
specific process.

Usage by agents:
- Recommendation Agent calls this to populate the "How to apply" section
- Can also be called standalone if a user asks "how do I apply for [program]?"
"""

import json
from pathlib import Path
from typing import Optional

from strands import tool

_DATA_DIR = Path(__file__).parent.parent / "data"


def _load_program(program_id: str) -> dict:
    path = _DATA_DIR / "programs" / f"{program_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


@tool(
    name="application_finder",
    description=(
        "Finds the application URL, required documents, and process notes "
        "for a specific benefit program in a specific state. Returns the "
        "state-specific URL if available, otherwise falls back to the federal URL."
    ),
)
def application_finder(
    program_id: str,
    state: str,
) -> dict:
    """Find the application details for a benefit program in a specific state.

    Args:
        program_id: The program identifier (e.g., 'snap', 'medicaid', 'wic').
        state: Two-letter US state code (e.g., 'CA', 'TX').
    """
    try:
        program = _load_program(program_id)
    except FileNotFoundError:
        return {
            "status": "error",
            "content": [{"text": f"Program data file not found: {program_id}.json"}],
        }

    state = state.upper()
    application = program.get("application", {})
    state_urls = application.get("state_urls", {})
    documents = program.get("documents_needed", [])

    state_url = state_urls.get(state)
    federal_url = application.get("federal_url", application.get("universal_application"))
    notes = application.get("notes", "")

    state_override = program.get("state_overrides", {}).get(state, {})
    state_program_name = state_override.get("program_name") or state_override.get("name")
    state_notes = state_override.get("notes", "")

    if state_url:
        url_source = "state_specific"
        apply_url = state_url
        guidance = f"Apply directly at {state_url}"
    elif federal_url:
        url_source = "federal_fallback"
        apply_url = federal_url
        guidance = (
            f"No state-specific application URL found for {state}. "
            f"Use the federal site at {federal_url} or search for "
            f"'{program.get('name', program_id)} application {state}' "
            f"to find your state's portal."
        )
    else:
        url_source = "none"
        apply_url = None
        guidance = (
            f"No application URL available. Contact your local "
            f"{program.get('agency', 'administering agency')} office "
            f"or call 211 for assistance."
        )

    return {
        "status": "success",
        "content": [
            {
                "json": {
                    "program_id": program_id,
                    "program_name": program.get("name", program_id),
                    "state_program_name": state_program_name,
                    "state": state,
                    "apply_url": apply_url,
                    "url_source": url_source,
                    "guidance": guidance,
                    "documents_needed": documents,
                    "application_notes": notes,
                    "state_notes": state_notes,
                    "agency": program.get("agency", ""),
                }
            }
        ],
    }
