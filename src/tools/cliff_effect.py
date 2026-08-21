"""
Cliff Effect Tool — detects benefit cliffs for eligible programs.

Calls PolicyEngine at income + $500/month to show whether a small income
increase causes a disproportionate loss in benefits. This helps users
understand the trade-off before taking a second job or raise.

The Recommendation Agent calls this only for high-value programs where
the household income is within a meaningful range of the threshold.
Agents decide which programs to check — the tool just runs the numbers.
"""

import copy
import json

from strands import tool

from src.tools.eligibility_checker import eligibility_checker


@tool(
    name="estimate_cliff_effect",
    description=(
        "Checks whether earning $500/month more would cause the household to lose "
        "eligibility or receive significantly less from a specific program. "
        "Returns the current vs projected benefit and whether a cliff exists. "
        "Call only for programs where eligible=true and the household income is "
        "likely near the eligibility threshold."
    ),
)
def estimate_cliff_effect(
    program_id: str,
    current_monthly_income: float,
    eligibility_profile: str,
) -> dict:
    """Check for a benefit cliff at income + $500/month.

    Args:
        program_id: Program to check (e.g., 'snap', 'medicaid').
        current_monthly_income: Household's current monthly income in dollars.
        eligibility_profile: JSON string of the full eligibility profile
            (same format as passed to eligibility_checker).
    """
    if current_monthly_income < 0 or current_monthly_income > 500_000 / 12:
        return {
            "status": "error",
            "content": [{"text": f"Invalid monthly income: {current_monthly_income}"}],
        }

    try:
        profile = json.loads(eligibility_profile)
    except (json.JSONDecodeError, TypeError):
        return {
            "status": "error",
            "content": [{"text": "eligibility_profile must be a valid JSON string"}],
        }

    # Build the +$500 scenario — deep copy to avoid mutating the original profile
    projected_profile = copy.deepcopy(profile)
    projected_income = current_monthly_income + 500
    projected_profile["monthly_income"] = projected_income

    adults = projected_profile.get("adults", [{"age": 30, "income": current_monthly_income * 12}])
    if adults:
        adults[0]["income"] = projected_income * 12
    projected_profile["adults"] = adults

    raw = eligibility_checker(json.dumps(projected_profile))
    if raw.get("status") != "success":
        return {
            "status": "error",
            "content": [{"text": "PolicyEngine call failed for cliff projection"}],
        }

    projected_programs = raw["content"][0]["json"]["programs"]

    if program_id not in projected_programs:
        return {
            "status": "error",
            "content": [{"text": f"program_id '{program_id}' not found in PolicyEngine results. Check spelling."}],
        }

    projected = projected_programs[program_id]
    proj_eligible = projected.get("eligible", False)
    proj_monthly = (projected.get("estimated_benefit") or {}).get("monthly", 0) or 0

    return {
        "status": "success",
        "content": [
            {
                "json": {
                    "program_id": program_id,
                    "current_monthly_income": current_monthly_income,
                    "projected_monthly_income": projected_income,
                    "projected_eligible": proj_eligible,
                    "projected_monthly_benefit": proj_monthly,
                    "cliff_detected": not proj_eligible,
                }
            }
        ],
    }
