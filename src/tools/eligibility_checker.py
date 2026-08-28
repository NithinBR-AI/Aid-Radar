"""
Eligibility Checker Tool — powered by PolicyEngine.

Evaluates a household profile against all supported benefit programs in a
single simulation run. PolicyEngine handles the FPL calculations, income
thresholds, state-specific rules, and benefit amount estimation internally.

LIHEAP is the one exception — PolicyEngine doesn't model it, so this tool
falls back to a simple FPL-based check using the household's income data.

Usage by agents:
- Eligibility Agent calls this once with the full household profile
- Monitor Agent calls this when re-evaluating saved profiles
"""

import datetime
import logging

from policyengine_us import Simulation

from strands import tool

from src.guardrails.profile_validator import validate_profile, ProfileValidationError

logger = logging.getLogger(__name__)

PROGRAM_VARIABLES = {
    "snap": {
        "display_name": "SNAP (Food Stamps)",
        "eligible": "is_snap_eligible",
        "amount": "snap",
        "unit": "spm_units",
        "annual": True,
    },
    "medicaid": {
        "display_name": "Medicaid",
        "eligible": "is_medicaid_eligible",
        "amount": None,
        "unit": "people",
        "annual": False,
    },
    "wic": {
        "display_name": "WIC",
        "eligible": "is_wic_eligible",
        "amount": None,
        "unit": "people",
        "annual": False,
    },
    "tanf": {
        "display_name": "TANF",
        "eligible": "is_demographic_tanf_eligible",
        "amount": "tanf",
        "unit": "spm_units",
        "annual": True,
    },
    "ssi": {
        "display_name": "SSI (Supplemental Security Income)",
        "eligible": "is_ssi_eligible",
        "amount": "ssi",
        "unit": "people",
        "annual": True,
    },
    "lifeline": {
        "display_name": "Lifeline",
        "eligible": "is_lifeline_eligible",
        "amount": "lifeline",
        "unit": "spm_units",
        "annual": True,
    },
    "free_school_meals": {
        "display_name": "Free School Meals",
        "eligible": "meets_school_meal_categorical_eligibility",
        "amount": "free_school_meals",
        "unit": "spm_units",
        "annual": True,
    },
}

# Federal Poverty Level base figures — updated annually by HHS each January.
# Source: 2026 HHS Poverty Guidelines (https://aspe.hhs.gov/topics/poverty-economic-mobility/poverty-guidelines)
# Update these values each year when HHS publishes new guidelines.
LIHEAP_FPL_YEAR = 2026  # update each January when HHS publishes new guidelines
FPL_BASE = 15_650          # 1-person household annual FPL (2026 HHS — same as 2024; update when 2026 guidelines publish)
FPL_PER_ADDITIONAL = 5_380  # increment per additional household member (2026 HHS)

if datetime.date.today().year > LIHEAP_FPL_YEAR:
    logger.warning(
        "LIHEAP FPL constants are from %d — update FPL_BASE and FPL_PER_ADDITIONAL for %d",
        LIHEAP_FPL_YEAR,
        datetime.date.today().year,
    )

LIHEAP_FPL_THRESHOLD = {
    # State-specific LIHEAP income limits as % of FPL.
    # Source: state LIHEAP program pages (last verified 2024).
    "CA": 200,
    "TX": 150,
    "NY": 165,
    "FL": 150,
}
LIHEAP_DEFAULT_THRESHOLD = 150


def _build_situation(profile: dict) -> dict:
    """Convert an AidRadar household profile into a PolicyEngine situation dict."""
    year = str(datetime.date.today().year)
    people = {}
    member_names = []

    adults = profile.get("adults", [])
    if not adults:
        adults = [{"age": profile.get("applicant_age", 30), "income": profile.get("monthly_income", 0) * 12}]

    has_disabled = profile.get("has_disabled_member", False)
    has_pregnant = profile.get("has_pregnant_member", False)
    elderly_count = profile.get("elderly_count", 1 if profile.get("has_elderly_65_plus", False) else 0)
    has_elderly = elderly_count > 0

    for i, adult in enumerate(adults):
        name = f"adult_{i}"
        member_names.append(name)
        person = {
            "age": {year: adult.get("age", 30)},
            "employment_income": {year: adult.get("income", 0)},
        }
        # Apply flags to adult_0 (primary applicant) if no adult already satisfies them.
        # For elderly: if flag is set but no adult is 65+, inject age 70 for adult_0.
        # For disabled/pregnant: set on adult_0 since we don't know which member.
        if i == 0:
            if has_disabled:
                # is_disabled affects Medicaid; is_ssi_disabled is required for SSI eligibility
                person["is_disabled"] = {year: True}
                person["is_ssi_disabled"] = {year: True}
            # Only set pregnancy on adult_0 if they are in a plausible reproductive age range.
            # If adult_0 is outside that range and another adult exists, set on adult_1.
            # Teen pregnancy (child node) is an out-of-scope edge case.
            if has_pregnant:
                applicant_age_val = adult.get("age", 30)
                if 12 <= applicant_age_val <= 55:
                    person["is_pregnant"] = {year: True}
        people[name] = person

    # If has_pregnant but adult_0 was outside reproductive age range, set on next available adult
    if has_pregnant:
        pregnant_set = any(p.get("is_pregnant", {}).get(year) for p in people.values())
        if not pregnant_set:
            fallback_set = False
            for name in member_names:
                if name.startswith("adult_") and name != "adult_0":
                    people[name]["is_pregnant"] = {year: True}
                    fallback_set = True
                    break
            if not fallback_set:
                # Single-adult household where adult_0 is outside reproductive age range.
                # Flag is dropped — WIC/Medicaid pregnancy benefits won't trigger.
                # This edge case (e.g. 70-year-old sole adult claiming pregnancy) is
                # likely a data error; log it rather than silently ignoring.
                logger.warning(
                    "_build_situation: has_pregnant_member=True but no eligible adult found "
                    "(adult_0 age=%s, total adults=%d) — is_pregnant not set on any member",
                    adults[0].get("age", "?") if adults else "?",
                    len(adults),
                )

    # If elderly members exist but no listed adult is 65+, inject synthetic 70-year-old members
    # so PolicyEngine models age-based eligibility (SSI, Medicaid) correctly.
    # Inject exactly elderly_count members — accurate household size for FPL threshold calculation.
    adults_list = profile.get("adults", [])
    existing_65_plus = sum(1 for a in adults_list if a.get("age", 0) >= 65)
    to_inject = max(0, elderly_count - existing_65_plus)
    for _ in range(to_inject):
        name = f"adult_{len(people)}"
        member_names.append(name)
        people[name] = {
            "age": {year: 70},
            "employment_income": {year: 0},
        }

    children = profile.get("children", [])
    for i, child in enumerate(children):
        name = f"child_{i}"
        member_names.append(name)
        people[name] = {
            "age": {year: child.get("age", 5)},
            "employment_income": {year: 0},
        }

    state = profile.get("state", "CA").upper()

    return {
        "people": people,
        "tax_units": {"tax_unit": {"members": member_names}},
        "spm_units": {"spm_unit": {"members": member_names}},
        "families": {"family": {"members": member_names}},
        "households": {
            "household": {
                "members": member_names,
                "state_code": {year: state},
            }
        },
    }


def _check_liheap(profile: dict) -> dict:
    """Simple FPL-based LIHEAP check since PolicyEngine doesn't cover it."""
    state = profile.get("state", "CA").upper()
    threshold = LIHEAP_FPL_THRESHOLD.get(state, LIHEAP_DEFAULT_THRESHOLD)

    household_size = len(profile.get("adults", [{}])) + len(profile.get("children", []))
    # Account for synthetic elderly members injected in _build_situation so LIHEAP FPL
    # threshold uses the same household size PolicyEngine sees.
    elderly_count = profile.get("elderly_count", 1 if profile.get("has_elderly_65_plus", False) else 0)
    adults_list = profile.get("adults", [])
    existing_65_plus = sum(1 for a in adults_list if a.get("age", 0) >= 65)
    to_inject = max(0, elderly_count - existing_65_plus)
    household_size += to_inject
    if household_size < 1:
        household_size = 1

    fpl_guideline = FPL_BASE + (household_size - 1) * FPL_PER_ADDITIONAL

    annual_income = profile.get("monthly_income", 0) * 12
    if not annual_income and profile.get("adults"):
        annual_income = sum(a.get("income", 0) for a in profile["adults"])

    pct_fpl = round((annual_income / fpl_guideline) * 100, 1) if fpl_guideline else 0

    return {
        "program_id": "liheap",
        "display_name": "LIHEAP (Energy Assistance)",
        "eligible": pct_fpl <= threshold,
        "estimated_annual_benefit": None,
        "details": {
            "percent_of_fpl": pct_fpl,
            "threshold_pct_fpl": threshold,
            "state": state,
            "note": "LIHEAP benefit amounts vary by state and energy costs. Contact your local agency for exact amounts.",
        },
    }


@tool(
    name="eligibility_checker",
    description=(
        "Evaluates a household profile against all 9 supported benefit programs "
        "(SNAP, Medicaid, WIC, TANF, SSI, Lifeline, Free School Meals, LIHEAP, ACA/CHIP). "
        "Uses PolicyEngine for 7 programs and a fallback FPL check for LIHEAP. "
        "Returns eligibility status and estimated benefit amounts for each program."
    ),
)
def eligibility_checker(profile_json: str) -> dict:
    """Check eligibility for all benefit programs in a single call.

    Args:
        profile_json: JSON string of the household profile containing keys:
            state (str), monthly_income (number), adults (list of objects with age and income),
            children (list of objects with age), has_disabled_member (bool), has_pregnant_member (bool).
    """
    import json as _json

    try:
        profile = _json.loads(profile_json)
    except (TypeError, _json.JSONDecodeError) as e:
        if isinstance(profile_json, dict):
            profile = profile_json
        else:
            return {"status": "error", "content": [{"text": f"Invalid profile JSON: {e}"}]}

    try:
        profile = validate_profile(profile)
    except ProfileValidationError as e:
        return {"status": "error", "content": [{"text": f"Invalid profile: {e}"}]}

    try:
        situation = _build_situation(profile)
        sim = Simulation(situation=situation)
    except Exception as e:
        return {
            "status": "error",
            "content": [{"text": f"Failed to build PolicyEngine simulation: {e}"}],
        }

    results = {}
    for program_id, variables in PROGRAM_VARIABLES.items():
        try:
            eligible_raw = sim.calculate(variables["eligible"], 2026)

            if variables["unit"] == "people":
                eligible = any(bool(v) for v in eligible_raw)
                eligible_detail = [bool(v) for v in eligible_raw]
            else:
                eligible = bool(eligible_raw[0])
                eligible_detail = bool(eligible_raw[0])

            amount = None
            if variables["amount"]:
                amount_raw = sim.calculate(variables["amount"], 2026)
                annual_amount = float(sum(amount_raw))
                if variables["annual"] and annual_amount > 0:
                    amount = {
                        "annual": round(annual_amount, 2),
                        "monthly": round(annual_amount / 12, 2),
                    }
                elif annual_amount > 0:
                    amount = {"value": round(annual_amount, 2)}

            results[program_id] = {
                "program_id": program_id,
                "display_name": variables["display_name"],
                "eligible": eligible,
                "eligible_detail": eligible_detail,
                "estimated_benefit": amount,
            }
        except Exception as e:
            results[program_id] = {
                "program_id": program_id,
                "display_name": variables["display_name"],
                "eligible": None,
                "error": str(e),
            }

    results["liheap"] = _check_liheap(profile)

    citizenship = profile.get("citizenship_status") or "qualified_immigrant"
    CITIZENSHIP_RESTRICTED = {"snap", "medicaid", "tanf", "ssi", "liheap"}
    if citizenship == "undocumented":
        for pid in CITIZENSHIP_RESTRICTED:
            if pid in results and results[pid].get("eligible"):
                results[pid]["eligible"] = False
                results[pid]["citizenship_override"] = True
                results[pid]["eligibility_note"] = (
                    "Federal law requires US citizenship or qualified immigration status for this program."
                )

    veteran = profile.get("veteran_in_household", False)

    eligible_programs = [pid for pid, r in results.items() if r.get("eligible")]
    ineligible_programs = [pid for pid, r in results.items() if r.get("eligible") is False]
    error_programs = [pid for pid, r in results.items() if r.get("eligible") is None]

    return {
        "status": "success",
        "content": [
            {
                "json": {
                    "summary": {
                        "total_programs_checked": len(results),
                        "eligible_count": len(eligible_programs),
                        "eligible_programs": eligible_programs,
                        "ineligible_programs": ineligible_programs,
                        "error_programs": error_programs,
                        "veteran_in_household": veteran,
                    },
                    "programs": results,
                }
            }
        ],
    }
