"""
AidRadar Evals — 5 household profiles against known expected outcomes.

Tests both:
  1. Tool accuracy  — eligibility_checker (PolicyEngine) returns expected programs
  2. Agent quality  — Recommendation Agent output contains required elements

Run: python -m evals.evals
"""

import json
import re
import sys

from src.tools.eligibility_checker import eligibility_checker
from src.agents import (
    create_intake_agent,
    create_eligibility_agent,
    create_recommendation_agent,
    create_monitor_agent,
)
from src.pipeline.runner import _call_agent_with_timeout
from src.tools.application_finder import application_finder
from src.tools.cliff_effect import estimate_cliff_effect
from src.tools.policy_change import check_policy_change
from src.tools.profile_history import get_profile_history

# ---------------------------------------------------------------------------
# Profiles + expected outcomes
# ---------------------------------------------------------------------------

PROFILES = [
    {
        "id": "ca_low_income_family",
        "description": "Low-income CA family — 2 adults, 2 kids, $1,800/mo",
        "profile": {
            "state": "CA",
            "monthly_income": 1800,
            "adults": [{"age": 32, "income": 21600}, {"age": 30, "income": 0}],
            "children": [{"age": 3}, {"age": 7}],
            "has_disabled_member": False,
            "has_pregnant_member": False,
            "citizenship_status": "us_citizen",
        },
        "expect_eligible": ["snap", "medicaid", "wic", "free_school_meals", "liheap"],
        "expect_ineligible": ["ssi"],
    },
    {
        "id": "tx_elderly_disabled",
        "description": "Elderly disabled TX adult — single, 68yo, $900/mo",
        "profile": {
            "state": "TX",
            "monthly_income": 900,
            "adults": [{"age": 68, "income": 10800}],
            "children": [],
            "elderly_count": 1,
            "has_disabled_member": True,
            "has_pregnant_member": False,
            "citizenship_status": "us_citizen",
        },
        # SSI now correctly triggers: is_ssi_disabled=True + age 68 (65+) + low income
        "expect_eligible": ["snap", "medicaid", "ssi", "liheap", "lifeline"],
        "expect_ineligible": ["wic", "tanf"],
    },
    {
        "id": "ny_higher_income_single",
        "description": "Higher-income NY single adult — $4,500/mo, no kids",
        "profile": {
            "state": "NY",
            "monthly_income": 4500,
            "adults": [{"age": 35, "income": 54000}],
            "children": [],
            "has_disabled_member": False,
            "has_pregnant_member": False,
            "citizenship_status": "us_citizen",
        },
        "expect_eligible": [],
        "expect_ineligible": ["snap", "medicaid", "wic", "tanf", "ssi", "liheap"],
    },
    {
        "id": "fl_undocumented_family",
        "description": "Undocumented FL family — citizenship override blocks restricted programs",
        "profile": {
            "state": "FL",
            "monthly_income": 1200,
            "adults": [{"age": 28, "income": 14400}],
            "children": [{"age": 4}],
            "has_disabled_member": False,
            "has_pregnant_member": False,
            "citizenship_status": "undocumented",
        },
        "expect_eligible": ["wic"],          # WIC is state-funded in FL, not citizenship-restricted
        "expect_ineligible": ["snap", "medicaid", "tanf", "ssi", "liheap"],
    },
    {
        "id": "ny_pregnant_low_income",
        "description": "Pregnant NY woman — low income, should trigger WIC",
        "profile": {
            "state": "NY",
            "monthly_income": 1500,
            "adults": [{"age": 24, "income": 18000}],
            "children": [],
            "has_disabled_member": False,
            "has_pregnant_member": True,
            "citizenship_status": "us_citizen",
        },
        "expect_eligible": ["snap", "medicaid", "wic", "liheap"],
        "expect_ineligible": ["ssi", "free_school_meals"],
    },
    {
        "id": "ca_veteran_mid_income",
        "description": "CA veteran household — 1 adult, $2,200/mo, veteran flag",
        "profile": {
            "state": "CA",
            "monthly_income": 2200,
            "adults": [{"age": 45, "income": 26400}],
            "children": [],
            "elderly_count": 0,
            "has_disabled_member": False,
            "has_pregnant_member": False,
            "citizenship_status": "us_citizen",
            "veteran_in_household": True,
        },
        "expect_eligible": ["medicaid", "lifeline", "liheap"],
        "expect_ineligible": ["wic", "free_school_meals", "ssi"],
    },
    {
        "id": "tx_large_family",
        "description": "Large TX family — 2 adults, 4 kids, $2,600/mo (FPL shifts with size)",
        "profile": {
            "state": "TX",
            "monthly_income": 2600,
            "adults": [{"age": 35, "income": 31200}, {"age": 33, "income": 0}],
            "children": [{"age": 2}, {"age": 5}, {"age": 8}, {"age": 11}],
            "has_disabled_member": False,
            "has_pregnant_member": False,
            "citizenship_status": "us_citizen",
        },
        "expect_eligible": ["snap", "medicaid", "wic", "free_school_meals", "liheap"],
        "expect_ineligible": ["ssi"],
    },
    {
        "id": "fl_single_parent_school_age",
        "description": "FL single parent — 1 adult, 2 school-age kids, $1,600/mo",
        "profile": {
            "state": "FL",
            "monthly_income": 1600,
            "adults": [{"age": 29, "income": 19200}],
            "children": [{"age": 8}, {"age": 12}],
            "has_disabled_member": False,
            "has_pregnant_member": False,
            "citizenship_status": "us_citizen",
        },
        "expect_eligible": ["snap", "medicaid", "free_school_meals", "liheap"],
        "expect_ineligible": ["ssi", "wic"],
    },
    {
        "id": "ny_near_threshold",
        "description": "NY single adult — income right at SNAP boundary, $2,100/mo",
        "profile": {
            "state": "NY",
            "monthly_income": 2100,
            "adults": [{"age": 40, "income": 25200}],
            "children": [],
            "has_disabled_member": False,
            "has_pregnant_member": False,
            "citizenship_status": "us_citizen",
        },
        "expect_eligible": ["medicaid", "liheap"],
        "expect_ineligible": ["wic", "free_school_meals", "ssi", "tanf"],
    },
    {
        "id": "ca_mixed_citizenship",
        "description": "CA mixed-citizenship household — 1 citizen adult, 1 non-citizen adult, 1 child",
        "profile": {
            "state": "CA",
            "monthly_income": 1400,
            "adults": [{"age": 30, "income": 16800}, {"age": 28, "income": 0}],
            "children": [{"age": 4}],
            "has_disabled_member": False,
            "has_pregnant_member": False,
            "citizenship_status": "qualified_immigrant",
        },
        "expect_eligible": ["snap", "medicaid", "wic", "liheap"],
        "expect_ineligible": ["ssi", "free_school_meals"],
    },
]

# ---------------------------------------------------------------------------
# Tool eval — eligibility_checker accuracy
# ---------------------------------------------------------------------------

def run_tool_evals() -> list[dict]:
    results = []
    print("\n" + "=" * 60)
    print("  TOOL EVALS — eligibility_checker (PolicyEngine)")
    print("=" * 60)

    for case in PROFILES:
        print(f"\n[{case['id']}] {case['description']}")
        raw = eligibility_checker(json.dumps(case["profile"]))

        if raw.get("status") != "success":
            print(f"  ERROR: eligibility_checker failed — {raw}")
            results.append({"id": case["id"], "passed": False, "errors": ["tool_error"]})
            continue

        programs = raw["content"][0]["json"]["programs"]
        errors = []

        for pid in case["expect_eligible"]:
            eligible = programs.get(pid, {}).get("eligible")
            if not eligible:
                errors.append(f"expected ELIGIBLE: {pid} (got {eligible})")
            else:
                print(f"  PASS  {pid} → eligible")

        for pid in case["expect_ineligible"]:
            eligible = programs.get(pid, {}).get("eligible")
            if eligible:
                errors.append(f"expected INELIGIBLE: {pid} (got {eligible})")
            else:
                print(f"  PASS  {pid} → ineligible")

        if errors:
            for e in errors:
                print(f"  FAIL  {e}")

        results.append({
            "id": case["id"],
            "passed": len(errors) == 0,
            "errors": errors,
        })

    return results


# ---------------------------------------------------------------------------
# Agent eval 1 — Intake Agent: extracts complete profile from conversation
# ---------------------------------------------------------------------------

INTAKE_CONVERSATION = [
    "I live in California",
    "My household has 2 adults and 2 kids aged 3 and 7",
    "We make about $1,800 a month",
    "No disabilities, no one is pregnant, we are US citizens",
]

INTAKE_REQUIRED_FIELDS = [
    "state", "monthly_income", "household_size", "applicant_age",
    "elderly_count", "has_disabled_member", "has_pregnant_member",
    "children_under_5", "children_k12", "veteran_in_household",
    "current_programs", "citizenship_status",
]

def run_intake_eval() -> dict:
    print("\n" + "=" * 60)
    print("  AGENT EVAL 1 — Intake Agent: profile extraction")
    print("=" * 60)

    agent = create_intake_agent()
    # Prime the agent
    agent(
        "Start the intake interview. The user's reply is coming next. "
        "Do NOT re-greet. Ask what state they live in."
    )

    output = ""
    for turn in INTAKE_CONVERSATION:
        print(f"  User: {turn}")
        result = agent(turn)
        output = str(result)

    # Extract JSON profile from final output
    match = re.search(r"\{.*\}", output, re.DOTALL)
    profile = {}
    if match:
        try:
            profile = json.loads(match.group())
        except json.JSONDecodeError:
            pass

    errors = []
    for field in INTAKE_REQUIRED_FIELDS:
        if field not in profile:
            errors.append(f"missing field: '{field}'")
        else:
            print(f"  PASS  extracted '{field}' = {profile[field]}")

    # Spot-check values
    if profile.get("state", "").upper() not in ("CA", "CALIFORNIA"):
        errors.append(f"state mismatch: expected CA, got {profile.get('state')}")
    if profile.get("monthly_income") and not (1500 <= profile["monthly_income"] <= 2100):
        errors.append(f"income out of range: {profile.get('monthly_income')} (expected ~1800)")
    if profile.get("household_size") and profile["household_size"] != 4:
        errors.append(f"household_size mismatch: expected 4, got {profile.get('household_size')}")

    # Negative check — must not claim ineligible programs or fabricate data
    raw_text = output.lower()
    fabricated_fields = ["ssn", "social security number", "address", "bank"]
    for f in fabricated_fields:
        if f in raw_text:
            errors.append(f"agent output contains PII field: '{f}'")

    if errors:
        for e in errors:
            print(f"  FAIL  {e}")

    return {"id": "intake_agent", "passed": len(errors) == 0, "errors": errors}


# ---------------------------------------------------------------------------
# Agent eval 2 — Recommendation Agent: mentions specific eligible programs
# ---------------------------------------------------------------------------

def run_recommendation_eval() -> dict:
    print("\n" + "=" * 60)
    print("  AGENT EVAL 2 — Recommendation Agent: program coverage")
    print("=" * 60)

    case = PROFILES[0]  # CA family — SNAP, Medicaid, WIC, Free School Meals, LIHEAP eligible
    raw = eligibility_checker(json.dumps(case["profile"]))
    eligibility_text = json.dumps(raw["content"][0]["json"], indent=2)

    agent = create_recommendation_agent()
    prompt = (
        "Here is a household profile and eligibility results. "
        "Generate the full benefits report.\n\n"
        f"**Household Profile:**\n```json\n{json.dumps(case['profile'], indent=2)}\n```\n\n"
        f"**Eligibility Results:**\n{eligibility_text}"
    )

    print("  Running Recommendation Agent...")
    result = _call_agent_with_timeout(agent, prompt, _agent_tools=[estimate_cliff_effect])
    output = result.lower()

    # Must mention each eligible program by name and include apply/action guidance
    required = ["snap", "medicaid", "wic", "apply"]
    errors = []
    for keyword in required:
        if keyword not in output:
            errors.append(f"missing: '{keyword}'")
        else:
            print(f"  PASS  mentions '{keyword}'")

    # Negative check — must NOT claim SSI eligible (case profile has no disability/elderly)
    if "ssi" in output and "not eligible" not in output:
        errors.append("hallucination: SSI mentioned as eligible — profile has no disability/elderly flag")
    else:
        print("  PASS  did not hallucinate SSI eligibility")

    if errors:
        for e in errors:
            print(f"  FAIL  {e}")

    return {"id": "recommendation_agent", "passed": len(errors) == 0, "errors": errors}


# ---------------------------------------------------------------------------
# Agent eval 3 — Monitor Agent: identifies correct gained/lost programs
# ---------------------------------------------------------------------------

def run_monitor_eval() -> dict:
    print("\n" + "=" * 60)
    print("  AGENT EVAL 3 — Monitor Agent: correct diff from snapshots")
    print("=" * 60)

    case = PROFILES[0]  # CA family

    # Baseline: high income — fewer programs eligible
    high_income_profile = dict(case["profile"])
    high_income_profile["monthly_income"] = 5000
    high_income_profile["adults"] = [{"age": 32, "income": 60000}, {"age": 30, "income": 0}]
    raw_prev = eligibility_checker(json.dumps(high_income_profile))
    previous_snapshot = raw_prev["content"][0]["json"]["programs"]

    # New: low income (original) — more programs eligible
    raw_curr = eligibility_checker(json.dumps(case["profile"]))
    new_snapshot = raw_curr["content"][0]["json"]["programs"]

    # Compute expected gains (ineligible at high income → eligible at low income)
    expected_gained = [
        pid for pid in new_snapshot
        if new_snapshot[pid].get("eligible") and not previous_snapshot.get(pid, {}).get("eligible")
    ]
    print(f"  Expected gained programs: {expected_gained}")

    agent = create_monitor_agent()
    prompt = (
        "You are running a scheduled eligibility re-check. Income dropped from $5,000/mo to $1,800/mo.\n\n"
        "**Eligibility changes (already calculated — do NOT recalculate):**\n"
        f"- Newly eligible: {', '.join(expected_gained) if expected_gained else 'none'}\n"
        "- Lost eligibility: none\n\n"
        "Write a short notification (2-3 sentences) telling the user what changed and what to do next. "
        "Plain English, no JSON."
    )

    print("  Running Monitor Agent...")
    result = _call_agent_with_timeout(agent, prompt, _agent_tools=[get_profile_history, check_policy_change])
    output = result.lower()

    errors = []
    # Must mention at least one of the gained programs and include action guidance
    mentioned = [pid for pid in expected_gained if pid.replace("_", " ") in output or pid in output]
    if not mentioned:
        errors.append(f"did not mention any gained program from: {expected_gained}")
    else:
        print(f"  PASS  mentioned gained programs: {mentioned}")

    if "apply" not in output and "eligible" not in output:
        errors.append("missing action guidance (no 'apply' or 'eligible' in output)")
    else:
        print("  PASS  includes action guidance")

    if errors:
        for e in errors:
            print(f"  FAIL  {e}")

    return {"id": "monitor_agent", "passed": len(errors) == 0, "errors": errors}


# ---------------------------------------------------------------------------
# Agent eval 4 — Eligibility Agent: calls application_finder for eligible programs
# ---------------------------------------------------------------------------

def run_eligibility_agent_eval() -> dict:
    print("\n" + "=" * 60)
    print("  AGENT EVAL 4 — Eligibility Agent: calls application_finder")
    print("=" * 60)

    case = PROFILES[0]  # CA family — SNAP, Medicaid, WIC eligible
    raw = eligibility_checker(json.dumps(case["profile"]))
    programs = raw["content"][0]["json"]["programs"]

    agent = create_eligibility_agent()
    prompt = (
        "The pipeline has already run PolicyEngine. Here are the eligibility results for all 8 programs.\n\n"
        f"**Household Profile:**\n```json\n{json.dumps(case['profile'], indent=2)}\n```\n\n"
        f"**PolicyEngine Results:**\n```json\n{json.dumps(programs, indent=2)}\n```\n\n"
        "Now call application_finder for each eligible program, identify cascading eligibility, "
        "and build the structured output for the Recommendation Agent."
    )

    print("  Running Eligibility Agent...")
    result = _call_agent_with_timeout(agent, prompt, _agent_tools=[application_finder])
    output = result.lower()

    errors = []
    # Must mention application URLs or documents for eligible programs
    for keyword in ["application_url", "apply", "snap", "medicaid"]:
        if keyword not in output:
            errors.append(f"missing expected content: '{keyword}'")
        else:
            print(f"  PASS  output contains '{keyword}'")

    # Must not mention eligibility_checker (agent should not re-run it)
    if "eligibility_checker" in output:
        errors.append("agent attempted to call eligibility_checker (should not re-run PolicyEngine)")
    else:
        print("  PASS  did not call eligibility_checker")

    if errors:
        for e in errors:
            print(f"  FAIL  {e}")

    return {"id": "eligibility_agent_tool_use", "passed": len(errors) == 0, "errors": errors}


# ---------------------------------------------------------------------------
# Agent eval 5 — Recommendation Agent: cliff effect warning for near-threshold profile
# ---------------------------------------------------------------------------

def run_cliff_effect_eval() -> dict:
    print("\n" + "=" * 60)
    print("  AGENT EVAL 5 — Recommendation Agent: cliff effect warning")
    print("=" * 60)

    # CA veteran at $2,200/mo — likely near SNAP/Medicaid threshold, cliff warning expected
    case = next(c for c in PROFILES if c["id"] == "ca_veteran_mid_income")
    raw = eligibility_checker(json.dumps(case["profile"]))
    programs = raw["content"][0]["json"]["programs"]
    eligibility_text = json.dumps(raw["content"][0]["json"], indent=2)

    agent = create_recommendation_agent()
    prompt = (
        "Here is the household profile, eligibility results, and the full eligibility profile "
        "JSON (pass this to estimate_cliff_effect if you call it). "
        "Generate the full benefits report following your instructions.\n\n"
        f"**Household Profile:**\n```json\n{json.dumps(case['profile'], indent=2)}\n```\n\n"
        f"**Eligibility Profile (for estimate_cliff_effect):**\n```json\n{json.dumps(case['profile'], indent=2)}\n```\n\n"
        f"**Eligibility Agent Results:**\n{eligibility_text}\n\n"
        f"**Raw Programs (for cliff effect context):**\n```json\n{json.dumps(programs, indent=2)}\n```"
    )

    print("  Running Recommendation Agent (cliff effect check)...")
    result = _call_agent_with_timeout(agent, prompt, _agent_tools=[estimate_cliff_effect])
    output = result.lower()

    errors = []
    # Report must include veteran section
    if "veteran" not in output:
        errors.append("missing veteran section in report")
    else:
        print("  PASS  includes veteran section")

    # Must include standard report elements
    for keyword in ["medicaid", "apply", "disclaimer"]:
        if keyword not in output:
            errors.append(f"missing expected content: '{keyword}'")
        else:
            print(f"  PASS  output contains '{keyword}'")

    # Cliff warning or income note should appear for income-based programs
    cliff_mentioned = any(kw in output for kw in ["cliff", "income increases", "500", "benefit may drop"])
    if not cliff_mentioned:
        errors.append("no cliff warning detected — estimate_cliff_effect may not have been called")
    else:
        print("  PASS  cliff effect warning present")

    if errors:
        for e in errors:
            print(f"  FAIL  {e}")

    return {"id": "recommendation_cliff_effect", "passed": len(errors) == 0, "errors": errors}


# ---------------------------------------------------------------------------
# Agent eval 6 — Monitor Agent: policy_driven vs situation_driven narrative
# ---------------------------------------------------------------------------

def run_monitor_policy_eval() -> dict:
    print("\n" + "=" * 60)
    print("  AGENT EVAL 6 — Monitor Agent: policy change vs situation change")
    print("=" * 60)

    agent = create_monitor_agent()

    # Simulate a change with a real profile_id-less run (no DynamoDB needed)
    # The agent should call check_policy_change and produce a policy-framed narrative
    prompt = (
        "You are the AidRadar Monitor Agent running a scheduled re-check.\n\n"
        "**Profile ID:** not available — skip get_profile_history\n"
        "**State:** CA\n"
        "**Previous snapshot date:** 2024-01-01\n\n"
        "**Eligibility changes (pre-calculated by PolicyEngine — do NOT recalculate):**\n"
        "- Newly eligible: SNAP\n"
        "- Lost eligibility: none\n"
        "- Benefit amounts changed: none\n\n"
        "Follow your instructions: call check_policy_change for each changed program, "
        "then write the narrative. Plain English. 3-5 sentences."
    )

    print("  Running Monitor Agent (policy change detection)...")
    result = _call_agent_with_timeout(agent, prompt, _agent_tools=[get_profile_history, check_policy_change])
    output = result.lower()

    errors = []
    # Must mention SNAP
    if "snap" not in output:
        errors.append("did not mention SNAP in narrative")
    else:
        print("  PASS  mentions SNAP")

    # Must include action guidance
    if not any(kw in output for kw in ["apply", "eligible", "qualify"]):
        errors.append("missing action guidance")
    else:
        print("  PASS  includes action guidance")

    # Should reference policy or rules (since SNAP has a 2024 FPL change in changelog)
    policy_mentioned = any(kw in output for kw in ["federal", "guideline", "rule", "policy", "threshold", "poverty"])
    if not policy_mentioned:
        errors.append("no policy context in narrative — check_policy_change may not have been called")
    else:
        print("  PASS  references policy context")

    if errors:
        for e in errors:
            print(f"  FAIL  {e}")

    return {"id": "monitor_policy_change", "passed": len(errors) == 0, "errors": errors}


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def print_summary(tool_results: list[dict], agent_results: list[dict]):
    all_results = tool_results + agent_results
    passed = sum(1 for r in all_results if r["passed"])
    total = len(all_results)

    print("\n" + "=" * 60)
    print("  EVAL SUMMARY")
    print("=" * 60)
    for r in all_results:
        icon = "PASS" if r["passed"] else "FAIL"
        print(f"  [{icon}] {r['id']}")
        for e in r.get("errors", []):
            print(f"         → {e}")
    print(f"\n  {passed}/{total} passed")
    print("=" * 60)
    return passed == total


if __name__ == "__main__":
    tool_results = run_tool_evals()
    agent_results = [
        run_intake_eval(),
        run_eligibility_agent_eval(),
        run_recommendation_eval(),
        run_cliff_effect_eval(),
        run_monitor_eval(),
        run_monitor_policy_eval(),
    ]
    all_passed = print_summary(tool_results, agent_results)
    sys.exit(0 if all_passed else 1)
