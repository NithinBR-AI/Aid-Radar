"""
Quick validation that policyengine-us returns the data AidRadar needs.

Tests a sample household (single parent, 2 kids, $2000/mo income, California)
against our 7 target programs. LIHEAP is excluded — PolicyEngine doesn't cover it.

Run: python tests/test_policyengine.py
"""

from policyengine_us import Simulation
import json


def build_household():
    """Single parent, 2 kids (ages 3 and 8), $2000/mo in California."""
    return {
        "people": {
            "parent": {
                "age": {"2026": 30},
                "employment_income": {"2026": 24000},  # $2000/mo * 12
            },
            "child1": {
                "age": {"2026": 3},
                "employment_income": {"2026": 0},
            },
            "child2": {
                "age": {"2026": 8},
                "employment_income": {"2026": 0},
            },
        },
        "tax_units": {
            "tax_unit": {
                "members": ["parent", "child1", "child2"],
            }
        },
        "spm_units": {
            "spm_unit": {
                "members": ["parent", "child1", "child2"],
            }
        },
        "families": {
            "family": {
                "members": ["parent", "child1", "child2"],
            }
        },
        "households": {
            "household": {
                "members": ["parent", "child1", "child2"],
                "state_code": {"2026": "CA"},
            }
        },
    }


def test_programs():
    print("Building simulation for: single parent, 2 kids, $2000/mo, California\n")
    sim = Simulation(situation=build_household())

    checks = {
        "SNAP": {
            "eligible": "is_snap_eligible",
            "amount": "snap",
        },
        "Medicaid": {
            "eligible": "is_medicaid_eligible",
            "amount": None,
        },
        "WIC": {
            "eligible": "is_wic_eligible",
            "amount": None,
        },
        "TANF": {
            "eligible": "is_demographic_tanf_eligible",
            "amount": "tanf",
        },
        "SSI": {
            "eligible": "is_ssi_eligible",
            "amount": "ssi",
        },
        "Lifeline": {
            "eligible": "is_lifeline_eligible",
            "amount": "lifeline",
        },
        "Free School Meals": {
            "eligible": "meets_school_meal_categorical_eligibility",
            "amount": "free_school_meals",
        },
    }

    results = {}
    for program, variables in checks.items():
        print(f"--- {program} ---")
        try:
            eligible_val = sim.calculate(variables["eligible"], 2026)
            print(f"  Eligible: {eligible_val}")

            if variables["amount"]:
                amount_val = sim.calculate(variables["amount"], 2026)
                print(f"  Amount: {amount_val}")

            results[program] = "OK"
        except Exception as e:
            print(f"  ERROR: {e}")
            results[program] = f"FAIL: {e}"
        print()

    print("=" * 50)
    print("SUMMARY")
    print("=" * 50)
    for program, status in results.items():
        icon = "PASS" if status == "OK" else "FAIL"
        print(f"  [{icon}] {program}: {status}")


if __name__ == "__main__":
    test_programs()
