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

from policyengine_us import Simulation

from strands import tool

PROGRAM_VARIABLES = {
    "snap": {
        "eligible": "is_snap_eligible",
        "amount": "snap",
        "unit": "spm_units",
        "annual": True,
    },
    "medicaid": {
        "eligible": "is_medicaid_eligible",
        "amount": None,
        "unit": "people",
        "annual": False,
    },
    "wic": {
        "eligible": "is_wic_eligible",
        "amount": None,
        "unit": "people",
        "annual": False,
    },
    "tanf": {
        "eligible": "is_demographic_tanf_eligible",
        "amount": "tanf",
        "unit": "spm_units",
        "annual": True,
    },
    "ssi": {
        "eligible": "is_ssi_eligible",
        "amount": "ssi",
        "unit": "people",
        "annual": True,
    },
    "lifeline": {
        "eligible": "is_lifeline_eligible",
        "amount": "lifeline",
        "unit": "spm_units",
        "annual": True,
    },
    "free_school_meals": {
        "eligible": "meets_school_meal_categorical_eligibility",
        "amount": "free_school_meals",
        "unit": "spm_units",
        "annual": True,
    },
}

LIHEAP_FPL_THRESHOLD = {
    "CA": 200,
    "TX": 150,
    "NY": 165,
    "FL": 150,
}
LIHEAP_DEFAULT_THRESHOLD = 150


def _build_situation(profile: dict) -> dict:
    """Convert an AidRadar household profile into a PolicyEngine situation dict."""
    year = "2026"
    people = {}
    member_names = []

    adults = profile.get("adults", [])
    if not adults:
        adults = [{"age": profile.get("applicant_age", 30), "income": profile.get("monthly_income", 0) * 12}]

    for i, adult in enumerate(adults):
        name = f"adult_{i}"
        member_names.append(name)
        people[name] = {
            "age": {year: adult.get("age", 30)},
            "employment_income": {year: adult.get("income", 0)},
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
    if household_size < 1:
        household_size = 1

    fpl_base = 15650
    fpl_per_person = 5380
    fpl_guideline = fpl_base + (household_size - 1) * fpl_per_person

    annual_income = profile.get("monthly_income", 0) * 12
    if not annual_income and profile.get("adults"):
        annual_income = sum(a.get("income", 0) for a in profile["adults"])

    pct_fpl = round((annual_income / fpl_guideline) * 100, 1) if fpl_guideline else 0

    return {
        "program_id": "liheap",
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
        "Evaluates a household profile against all 8 supported benefit programs "
        "(SNAP, Medicaid, WIC, TANF, SSI, Lifeline, Free School Meals, LIHEAP). "
        "Uses PolicyEngine for 7 programs and a fallback FPL check for LIHEAP. "
        "Returns eligibility status and estimated benefit amounts for each program."
    ),
)
def eligibility_checker(profile: dict) -> dict:
    """Check eligibility for all benefit programs in a single call.

    Args:
        profile: Household profile from the Intake Agent containing:
            - state: Two-letter state code (e.g., 'CA')
            - monthly_income: Total monthly household income
            - adults: List of dicts with 'age' and 'income' (annual) keys
            - children: List of dicts with 'age' key
            - has_disabled_member: bool (optional)
            - has_pregnant_member: bool (optional)
    """
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
                "eligible": eligible,
                "eligible_detail": eligible_detail,
                "estimated_benefit": amount,
            }
        except Exception as e:
            results[program_id] = {
                "program_id": program_id,
                "eligible": None,
                "error": str(e),
            }

    results["liheap"] = _check_liheap(profile)

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
                    },
                    "programs": results,
                }
            }
        ],
    }
