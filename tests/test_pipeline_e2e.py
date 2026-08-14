"""End-to-end pipeline test with a pre-filled profile.

Skips the interactive Intake Agent and feeds a test household directly
into the Eligibility → Recommendation pipeline.

Usage:
    python -m tests.test_pipeline_e2e
"""

import json
import sys

from src.main import run_eligibility, run_recommendation

TEST_PROFILES = {
    "ca_family_low_income": {
        "state": "CA",
        "monthly_income": 2000,
        "applicant_age": 32,
        "household_size": 3,
        "children_under_5": [{"age": 4}],
        "children_k12": [{"age": 8}],
        "has_disabled_member": False,
        "has_pregnant_member": False,
        "has_elderly_65_plus": False,
        "current_programs": [],
        "veteran_in_household": False,
        "citizenship_status": "us_citizen",
        "income_is_approximate": False,
    },
    "tx_single_adult": {
        "state": "TX",
        "monthly_income": 1200,
        "applicant_age": 55,
        "household_size": 1,
        "children_under_5": [],
        "children_k12": [],
        "has_disabled_member": True,
        "has_pregnant_member": False,
        "has_elderly_65_plus": False,
        "current_programs": [],
        "veteran_in_household": True,
        "citizenship_status": "us_citizen",
        "income_is_approximate": False,
    },
    "ny_large_family": {
        "state": "NY",
        "monthly_income": 3500,
        "applicant_age": 40,
        "household_size": 6,
        "children_under_5": [{"age": 2}, {"age": 4}],
        "children_k12": [{"age": 7}, {"age": 12}],
        "has_disabled_member": False,
        "has_pregnant_member": True,
        "has_elderly_65_plus": False,
        "current_programs": [],
        "veteran_in_household": False,
        "citizenship_status": "us_citizen",
        "income_is_approximate": True,
    },
}


def run_test(profile_name: str):
    profile = TEST_PROFILES[profile_name]
    print(f"\n{'=' * 60}")
    print(f"  Testing profile: {profile_name}")
    print(f"{'=' * 60}")
    print(f"\n{json.dumps(profile, indent=2)}\n")

    eligibility_results = run_eligibility(profile)
    run_recommendation(eligibility_results, profile)

    print(f"\n{'=' * 60}")
    print(f"  Pipeline complete for: {profile_name}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "ca_family_low_income"
    if name not in TEST_PROFILES:
        print(f"Unknown profile: {name}")
        print(f"Available: {', '.join(TEST_PROFILES)}")
        sys.exit(1)
    run_test(name)
