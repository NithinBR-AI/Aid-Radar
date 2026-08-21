"""
AidRadar Guardrails — profile validation and PII scrubbing.

Called before eligibility_checker runs and before DynamoDB writes.
Handles LLM output normalization (string income, long state names, numpy types)
and strips PII patterns that should never be stored.
"""

import re

SUPPORTED_STATES = {"CA", "TX", "NY", "FL"}
FEDERAL_FALLBACK_STATE = "CA"  # PolicyEngine state used when user is out-of-supported-area

CITIZENSHIP_VALUES = {"us_citizen", "permanent_resident", "qualified_immigrant", "undocumented"}

CITIZENSHIP_NORMALIZATION = {
    "us citizen": "us_citizen",
    "citizen": "us_citizen",
    "united states citizen": "us_citizen",
    "permanent resident": "permanent_resident",
    "green card": "permanent_resident",
    "qualified immigrant": "qualified_immigrant",
    "immigrant": "qualified_immigrant",
    "undocumented": "undocumented",
    "unauthorized": "undocumented",
    "no status": "undocumented",
}

STATE_NAME_MAP = {
    "CALIFORNIA": "CA", "TEXAS": "TX", "NEW YORK": "NY", "FLORIDA": "FL",
}

_SSN_PATTERN = re.compile(r"\b\d{3}[-\s]\d{2}[-\s]\d{4}\b")
_ACCOUNT_PATTERN = re.compile(r"\b\d{8,17}\b")


class ProfileValidationError(ValueError):
    pass


def _coerce_number(val, field: str, min_val: float = 0, max_val: float = None) -> float:
    """Coerce a value to float, stripping currency symbols and commas."""
    if val is None:
        return 0.0
    if isinstance(val, str):
        cleaned = val.replace("$", "").replace(",", "").replace("/mo", "").strip()
        try:
            val = float(cleaned)
        except ValueError:
            raise ProfileValidationError(f"'{field}' must be a number, got: {val!r}")
    try:
        val = float(val)
    except (TypeError, ValueError):
        raise ProfileValidationError(f"'{field}' must be a number, got: {val!r}")
    if val < min_val:
        raise ProfileValidationError(f"'{field}' must be >= {min_val}, got {val}")
    if max_val is not None and val > max_val:
        raise ProfileValidationError(f"'{field}' must be <= {max_val}, got {val}")
    return val


def _normalize_state(state) -> str:
    """Normalize state to 2-letter code.

    For unsupported states, falls back to FEDERAL_FALLBACK_STATE so the intake
    prompt's promise ("we'll use federal thresholds") is honored rather than
    raising an error. The original state string is preserved in 'state_original'
    by the caller so downstream agents can disclose the fallback to the user.
    """
    if not state:
        raise ProfileValidationError("'state' is required")
    s = str(state).strip().upper()
    s = STATE_NAME_MAP.get(s, s)
    if s not in SUPPORTED_STATES:
        return FEDERAL_FALLBACK_STATE
    return s


def _scrub_pii(text: str) -> str:
    """Remove SSN and account number patterns from a string."""
    text = _SSN_PATTERN.sub("[REDACTED]", text)
    text = _ACCOUNT_PATTERN.sub("[REDACTED]", text)
    return text


def _scrub_dict(obj):
    """Recursively scrub PII from all string values in a dict/list."""
    if isinstance(obj, dict):
        return {k: _scrub_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_scrub_dict(i) for i in obj]
    if isinstance(obj, str):
        return _scrub_pii(obj)
    return obj


def validate_profile(profile: dict) -> dict:
    """
    Validate and normalize a household profile before passing to PolicyEngine.

    Returns a clean, normalized profile dict.
    Raises ProfileValidationError with a user-friendly message on invalid input.
    """
    if not isinstance(profile, dict):
        raise ProfileValidationError("Profile must be a JSON object.")

    cleaned = dict(profile)

    # State — preserve original so agents can disclose out-of-area fallback
    raw_state = str(profile.get("state", "")).strip().upper()
    raw_state = STATE_NAME_MAP.get(raw_state, raw_state)
    cleaned["state"] = _normalize_state(profile.get("state"))
    if raw_state not in SUPPORTED_STATES and raw_state:
        cleaned["state_original"] = raw_state
        cleaned["state_is_fallback"] = True

    # Income
    cleaned["monthly_income"] = _coerce_number(
        profile.get("monthly_income", 0), "monthly_income", min_val=0, max_val=500_000
    )

    # Adults
    adults = profile.get("adults", [])
    if not isinstance(adults, list):
        raise ProfileValidationError("'adults' must be a list.")
    cleaned_adults = []
    for i, adult in enumerate(adults):
        if not isinstance(adult, dict):
            raise ProfileValidationError(f"adults[{i}] must be an object.")
        cleaned_adults.append({
            "age": int(_coerce_number(adult.get("age", 30), f"adults[{i}].age", 0, 120)),
            "income": _coerce_number(adult.get("income", 0), f"adults[{i}].income", 0, 6_000_000),
        })
    cleaned["adults"] = cleaned_adults

    # Children
    children = profile.get("children", [])
    if not isinstance(children, list):
        raise ProfileValidationError("'children' must be a list.")
    cleaned_children = []
    for i, child in enumerate(children):
        if not isinstance(child, dict):
            raise ProfileValidationError(f"children[{i}] must be an object.")
        age = int(_coerce_number(child.get("age", 5), f"children[{i}].age", 0, 17))
        cleaned_children.append({"age": age})
    cleaned["children"] = cleaned_children

    # Household sanity check
    total = len(cleaned_adults) + len(cleaned_children)
    if total == 0:
        raise ProfileValidationError("Household must have at least 1 member.")
    if total > 20:
        raise ProfileValidationError("Household size exceeds maximum of 20.")
    if len(cleaned_adults) == 0:
        raise ProfileValidationError(
            "Household must have at least 1 adult. "
            "The number of children equals or exceeds the household size — please verify."
        )

    # Elderly count — normalize to int, derive has_elderly_65_plus for downstream compatibility
    raw_elderly = profile.get("elderly_count", profile.get("has_elderly_65_plus", 0))
    if isinstance(raw_elderly, bool):
        elderly_count = 1 if raw_elderly else 0
    else:
        try:
            elderly_count = max(0, int(float(str(raw_elderly))))
        except (ValueError, TypeError):
            elderly_count = 0
    cleaned["elderly_count"] = elderly_count
    has_elderly = elderly_count > 0

    # If elderly members exist and none of the listed adults are 65+, the elderly persons are
    # additional household members — verify household_size accounts for them.
    applicant_age = cleaned_adults[0]["age"] if cleaned_adults else 0
    has_65_plus_in_list = any(a["age"] >= 65 for a in cleaned_adults)
    non_elderly_adults = len(cleaned_adults) if has_65_plus_in_list else len(cleaned_adults)
    unaccounted_elderly = 0 if has_65_plus_in_list else elderly_count
    if unaccounted_elderly > 0 and len(cleaned_adults) < (1 + unaccounted_elderly):
        raise ProfileValidationError(
            f"You indicated {elderly_count} person(s) age 65 or older in the household, "
            "but the household size doesn't account for them. Please verify your household size."
        )

    # Pregnant/disabled flags are booleans — no headcount check needed, just normalize.
    cleaned["has_disabled_member"] = bool(profile.get("has_disabled_member", False))
    cleaned["has_pregnant_member"] = bool(profile.get("has_pregnant_member", False))
    cleaned["has_elderly_65_plus"] = has_elderly  # kept for downstream PolicyEngine wiring

    # Citizenship — normalize free-text LLM output to canonical values
    citizenship = profile.get("citizenship_status")
    if citizenship is not None:
        normalized = str(citizenship).strip().lower()
        citizenship = CITIZENSHIP_NORMALIZATION.get(normalized, normalized.replace(" ", "_"))
        if citizenship not in CITIZENSHIP_VALUES:
            # Default to qualified_immigrant (broadest eligible non-citizen category) rather than
            # us_citizen — avoids falsely granting full citizen eligibility to DACA/refugee/TPS holders.
            citizenship = "qualified_immigrant"
    cleaned["citizenship_status"] = citizenship

    # Scrub PII from all string fields
    cleaned = _scrub_dict(cleaned)

    return cleaned


def safe_serialize(obj):
    """
    JSON-safe serializer that converts numpy/non-standard types to Python natives.
    Use as the `default` arg in json.dumps() before DynamoDB writes.
    """
    try:
        import numpy as np
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.bool_):
            return bool(obj)
    except ImportError:
        pass
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
