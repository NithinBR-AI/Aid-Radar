"""
AidRadar Pipeline Runner — agent orchestration, decoupled from Streamlit UI.

Owns:
  - Profile extraction from agent text
  - Intake → Eligibility → Recommendation pipeline
  - What If eligibility re-calculation
  - Eligibility profile format conversion

The Streamlit app calls these functions; it never orchestrates agents directly.
"""

import copy
import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field

from src.agents import create_eligibility_agent, create_recommendation_agent
from src.config import FALLBACK_MODEL_IDS, create_mantle_model
from src.db.profile_store import save_profile
from src.models.eligibility_output import parse_eligibility_output
from src.tools.application_finder import application_finder
from src.tools.cliff_effect import estimate_cliff_effect
from src.tools.eligibility_checker import eligibility_checker
from src.guardrails.profile_validator import ProfileValidationError, validate_profile

logger = logging.getLogger(__name__)

# Maximum wall-clock seconds to wait for a single LLM agent call.
# Mantle/DeepSeek cold starts can be slow; 120s covers the 99th percentile.
# Beyond this the user gets a graceful error rather than an infinite spinner.
_AGENT_TIMEOUT_SECONDS = 120


_MANTLE_RETRY_CODES = {429, 503, 502, 500}
_MANTLE_RETRIES = 2
_MANTLE_RETRY_DELAY = 2  # seconds; doubles on each attempt
_FALLBACK_TRIGGER_CODES = {503, 502}  # persistent unavailability → try next model


def _call_agent_with_timeout(agent, prompt: str, timeout: int = _AGENT_TIMEOUT_SECONDS,
                              _fallback_index: int = 0, _agent_tools: list | None = None) -> str:
    """Call a Strands agent with a wall-clock timeout, retry, and model fallback.

    On 503/502 after retries, swaps to the next model in FALLBACK_MODEL_IDS and
    rebuilds the agent with that model. Falls through the fallback chain before
    raising. 429/500 retry on same model first.
    """
    last_error = None
    for attempt in range(1 + _MANTLE_RETRIES):
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(agent, prompt)
            try:
                return str(future.result(timeout=timeout))
            except FuturesTimeoutError:
                future.cancel()
                raise TimeoutError(f"Agent call exceeded {timeout}s timeout")
            except Exception as e:
                last_error = e
                status = getattr(getattr(e, "response", None), "status_code", None)
                if status in _MANTLE_RETRY_CODES and attempt < _MANTLE_RETRIES:
                    delay = _MANTLE_RETRY_DELAY * (2 ** attempt)
                    logger.warning("_call_agent_with_timeout retrying attempt=%d status=%s delay=%ds", attempt + 1, status, delay)
                    time.sleep(delay)
                    continue
                break

    # Try next fallback model if primary/previous fallback returned persistent 5xx
    status = getattr(getattr(last_error, "response", None), "status_code", None)
    if status in _FALLBACK_TRIGGER_CODES and _fallback_index < len(FALLBACK_MODEL_IDS):
        fallback_model_id = FALLBACK_MODEL_IDS[_fallback_index]
        logger.warning("_call_agent_with_timeout switching to fallback model=%s", fallback_model_id)
        fallback_model = create_mantle_model(model_id=fallback_model_id)
        from strands import Agent
        # Use the explicitly passed tools list — agent.tool_registry is internal Strands API.
        # Callers pass _agent_tools at the call site so fallback preserves the same tools.
        tools = _agent_tools if _agent_tools is not None else []
        fallback_agent = Agent(
            model=fallback_model,
            system_prompt=agent.system_prompt,
            tools=tools,
        )
        return _call_agent_with_timeout(fallback_agent, prompt, timeout, _fallback_index + 1, _agent_tools=tools)

    raise last_error


@dataclass
class PipelineResult:
    eligibility_text: str
    report_text: str
    programs: dict = field(default_factory=dict)
    profile_id: str | None = None
    error: str | None = None
    error_programs: list = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.error is None

    @property
    def monitoring_active(self) -> bool:
        """True if the profile was saved successfully and Monitor Agent can track changes."""
        return self.profile_id is not None


def extract_json_profile(text: str) -> dict | None:
    """Extract a JSON object from agent output.

    Prefers fenced code blocks (```json ... ```) as the authoritative source.
    Falls back to scanning for a balanced JSON object only when no fence is found.
    Returns None if parsing fails — callers must handle the None case explicitly.
    """
    # Preferred path: fenced code block
    pattern = r"```(?:json)?\s*(\{.*?\})\s*```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None

    # Fallback: find the outermost balanced JSON object.
    # This is a last resort — if the agent produces malformed output with
    # multiple JSON fragments, this will silently pick the wrong one.
    # Log a warning in production rather than silently returning garbage.
    brace_start = text.find("{")
    if brace_start == -1:
        return None

    depth = 0
    for i, ch in enumerate(text[brace_start:], start=brace_start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[brace_start:i + 1])
                except json.JSONDecodeError:
                    return None

    return None



def build_eligibility_profile(intake_profile: dict) -> dict:
    """Convert the Intake Agent's profile schema to what eligibility_checker expects.

    Intake Agent produces: monthly_income, applicant_age, household_size,
    children_under_5 (list), children_k12 (list), state, and boolean flags.

    eligibility_checker expects: monthly_income, adults (list with age+income),
    children (list with age), state, and the same boolean flags.

    Adults without explicit age/income data default to age=30, income=0.
    This is documented — the What If simulator notes the same limitation.
    """
    if not isinstance(intake_profile, dict):
        raise ValueError(f"intake_profile must be a dict, got {type(intake_profile)}")
    if not intake_profile.get("state"):
        raise ValueError("intake_profile is missing required field: state")

    monthly_income = intake_profile.get("monthly_income", 0)
    if not isinstance(monthly_income, (int, float)):
        try:
            monthly_income = float(str(monthly_income).replace("$", "").replace(",", ""))
        except (ValueError, TypeError):
            raise ValueError(f"intake_profile.monthly_income is not a number: {monthly_income!r}")

    # If the profile already has a structured adults list with per-person incomes
    # (e.g. from a direct API call or integration test), use it as-is.
    # Otherwise build from the Intake Agent's flat schema (one applicant_age + monthly_income).
    if intake_profile.get("adults") and isinstance(intake_profile["adults"], list):
        adults = [
            {"age": a.get("age", 30), "income": a.get("income", 0)}
            for a in intake_profile["adults"]
        ]
    else:
        applicant_age = intake_profile.get("applicant_age", 30)
        adults = [{"age": applicant_age, "income": monthly_income * 12}]

    children = []
    for child in intake_profile.get("children_under_5", []) or []:
        age = child.get("age") or 3
        children.append({"age": min(int(age), 4)})
    for child in intake_profile.get("children_k12", []) or []:
        age = child.get("age") or 10
        children.append({"age": max(5, min(int(age), 18))})
    # Also handle pre-structured children list (direct API / integration path)
    if not children and intake_profile.get("children") and isinstance(intake_profile["children"], list):
        children = [{"age": c.get("age", 5)} for c in intake_profile["children"]]

    household_size = intake_profile.get("household_size", 1)
    accounted_for = len(adults) + len(children)
    if household_size > accounted_for:
        for _ in range(household_size - accounted_for):
            adults.append({"age": 30, "income": 0})

    # Safety net: children >= household_size leaves 0 adults — PolicyEngine requires at least 1.
    # The intake prompt flags this conversationally; this guard catches any case that slips through.
    if len(adults) == 0:
        adults.append({"age": 30, "income": monthly_income * 12})

    return {
        "state": intake_profile.get("state", "CA"),
        "monthly_income": monthly_income,
        "adults": adults,
        "children": children,
        "has_disabled_member": intake_profile.get("has_disabled_member", False),
        "has_pregnant_member": intake_profile.get("has_pregnant_member", False),
        "elderly_count": intake_profile.get("elderly_count", 1 if intake_profile.get("has_elderly_65_plus", False) else 0),
        "has_elderly_65_plus": intake_profile.get("has_elderly_65_plus", False),
        "current_programs": intake_profile.get("current_programs", []),
        "veteran_in_household": intake_profile.get("veteran_in_household", False),
        "citizenship_status": intake_profile.get("citizenship_status"),
        "income_is_approximate": intake_profile.get("income_is_approximate", False),
    }


def run_pipeline(intake_profile: dict) -> PipelineResult:
    """
    Run PolicyEngine → Eligibility Agent → Recommendation Agent.

    PolicyEngine runs first as a direct call — deterministic, no LLM involved.
    The Eligibility Agent receives the results in its prompt and only calls
    application_finder to enrich with URLs and documents.
    This means programs is always authoritative, never parsed from free text.
    """
    try:
        eligibility_profile = build_eligibility_profile(intake_profile)
    except (ValueError, ProfileValidationError) as e:
        return PipelineResult(
            eligibility_text="",
            report_text="",
            error=f"validation_error:{e}",
        )

    # Warn if children were expected but none mapped through (silent schema mismatch)
    if eligibility_profile.get("household_size", 1) > len(eligibility_profile.get("adults", [])) and not eligibility_profile.get("children"):
        logger.warning(
            "run_pipeline household_size=%d adults=%d children=0 — children may have been dropped during profile conversion",
            eligibility_profile.get("household_size", 1),
            len(eligibility_profile.get("adults", [])),
        )

    # Step 1: PolicyEngine — direct call, authoritative result
    programs: dict = {}
    error_programs: list = []
    profile_id: str | None = None
    _t_pipeline_start = time.perf_counter()

    _t0 = time.perf_counter()
    raw = eligibility_checker(json.dumps(eligibility_profile))
    logger.info('{"stage":"policy_engine","duration_ms":%d,"status":"%s"}',
                int((time.perf_counter() - _t0) * 1000), raw.get("status", "unknown"))
    if raw.get("status") == "success":
        programs = raw["content"][0]["json"]["programs"]
        error_programs = [pid for pid, r in programs.items() if r.get("eligible") is None]
        if error_programs:
            logger.warning("run_pipeline error_programs=%s", error_programs)
        try:
            profile_id = save_profile(intake_profile, programs)
            logger.info("run_pipeline profile_saved profile_id=%s", profile_id)
        except Exception as e:
            logger.error("run_pipeline save_profile_failed error=%s", e)
            # profile_id stays None — PipelineResult.monitoring_active will be False
    else:
        logger.error("run_pipeline eligibility_checker_failed status=%s", raw.get("status"))

    # Step 2: Eligibility Agent — receives PolicyEngine results in prompt,
    # calls application_finder only, builds structured interpretation
    error_note = ""
    if error_programs:
        error_note = (
            f"\n\nThe following programs could not be assessed due to a PolicyEngine error "
            f"and must be disclosed to the user: {', '.join(p.upper() for p in error_programs)}. "
            "Tell the user these programs could not be evaluated and suggest they contact a benefits counselor."
        )

    agent = create_eligibility_agent()
    eligibility_prompt = (
        "The pipeline has already run PolicyEngine. Here are the eligibility results for all 8 programs.\n\n"
        f"**Household Profile:**\n```json\n{json.dumps(eligibility_profile, indent=2)}\n```\n\n"
        f"**PolicyEngine Results:**\n```json\n{json.dumps(programs, indent=2)}\n```\n\n"
        "Now call application_finder for each eligible program, identify cascading eligibility, "
        f"and build the structured output for the Recommendation Agent.{error_note}"
    )
    _t1 = time.perf_counter()
    try:
        eligibility_text = _call_agent_with_timeout(agent, eligibility_prompt, _agent_tools=[application_finder])
        parsed = parse_eligibility_output(eligibility_text)
        if parsed is None:
            logger.error("run_pipeline eligibility_agent_output failed schema validation — aborting pipeline")
            return PipelineResult(
                eligibility_text=eligibility_text,
                report_text="",
                programs=programs,
                profile_id=profile_id,
                error="The eligibility agent returned malformed output. Please try again.",
            )
        logger.info('{"stage":"eligibility_agent","duration_ms":%d,"schema_valid":true}',
                    int((time.perf_counter() - _t1) * 1000))
    except TimeoutError:
        logger.error("run_pipeline eligibility_agent_timeout exceeded=%ds", _AGENT_TIMEOUT_SECONDS)
        return PipelineResult(
            eligibility_text="",
            report_text="",
            programs=programs,
            profile_id=profile_id,
            error=f"The eligibility agent timed out after {_AGENT_TIMEOUT_SECONDS} seconds. Please try again.",
        )

    # Step 3: Recommendation Agent — receives raw programs dict and eligibility_profile
    # so it can call estimate_cliff_effect with the correct income and profile data.
    # Build a lean program summary for the recommendation prompt — only the fields
    # the Recommendation Agent actually needs (eligibility, benefit, cliff context).
    # Avoids re-sending the full eligibility_profile JSON that the Eligibility Agent already processed.
    program_summary = {
        pid: {
            "eligible": r.get("eligible"),
            "estimated_benefit": r.get("estimated_benefit") or r.get("details"),
            "display_name": r.get("display_name"),
        }
        for pid, r in programs.items()
    }

    rec_agent = create_recommendation_agent()
    rec_prompt = (
        "Generate the full benefits report following your instructions.\n\n"
        f"**Household Profile:**\n```json\n{json.dumps(intake_profile, indent=2)}\n```\n\n"
        f"**Eligibility Profile (pass this JSON string to estimate_cliff_effect):**\n```json\n{json.dumps(eligibility_profile, indent=2)}\n```\n\n"
        f"**Eligibility Agent Results:**\n{eligibility_text}\n\n"
        f"**Program Summary (eligibility + benefit amounts):**\n```json\n{json.dumps(program_summary, indent=2)}\n```"
    )
    _t2 = time.perf_counter()
    try:
        report_text = _call_agent_with_timeout(rec_agent, rec_prompt, _agent_tools=[estimate_cliff_effect])
        logger.info('{"stage":"recommendation_agent","duration_ms":%d}',
                    int((time.perf_counter() - _t2) * 1000))
    except TimeoutError:
        logger.error("run_pipeline recommendation_agent_timeout exceeded=%ds", _AGENT_TIMEOUT_SECONDS)
        return PipelineResult(
            eligibility_text=eligibility_text,
            report_text="",
            programs=programs,
            profile_id=profile_id,
            error=f"The recommendation agent timed out after {_AGENT_TIMEOUT_SECONDS} seconds. Please try again.",
        )

    eligible_count = len([p for p in programs.values() if p.get("eligible")])
    logger.info('{"stage":"pipeline_total","duration_ms":%d,"profile_id":"%s","eligible_count":%d}',
                int((time.perf_counter() - _t_pipeline_start) * 1000), profile_id or "none", eligible_count)

    return PipelineResult(
        eligibility_text=eligibility_text,
        report_text=report_text,
        programs=programs,
        profile_id=profile_id,
        error_programs=error_programs,
    )


def run_whatif(base_profile: dict, monthly_income: int, num_adults: int, num_children: int) -> dict:
    """Re-run eligibility_checker for a modified household. Returns programs dict."""
    # Guard: PolicyEngine requires at least 1 adult — slider min should enforce this
    # but we defend here too so a UI bug doesn't reach PolicyEngine.
    num_adults = max(1, num_adults)
    num_children = max(0, num_children)

    p = copy.deepcopy(base_profile)
    p["monthly_income"] = monthly_income

    annual = monthly_income * 12
    existing_adults = p.get("adults", [])
    # Simplification: all slider income is attributed to adult[0].
    # For multi-income households this differs from the actual intake profile,
    # but the What If simulator is an exploration tool, not a re-intake.
    p["adults"] = [
        {"age": existing_adults[i]["age"] if i < len(existing_adults) else 35,
         "income": annual if i == 0 else 0}
        for i in range(num_adults)
    ]

    existing_children = p.get("children", [])
    p["children"] = [
        {"age": existing_children[i]["age"] if i < len(existing_children) else 5}
        for i in range(num_children)
    ]

    result = eligibility_checker(json.dumps(p))
    if result.get("status") != "success":
        return {}
    return result["content"][0]["json"]["programs"]
