"""
AidRadar Guardrails — profile validation and PII scrubbing.

Called before eligibility_checker runs and before DynamoDB writes.
Handles LLM output normalization (string income, long state names, numpy types)
and strips PII patterns that should never be stored.
"""

import re

SUPPORTED_STATES = {"CA", "TX", "NY", "FL"}

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
    """Normalize state to 2-letter code. Raises if unsupported."""
    if not state:
        raise ProfileValidationError("'state' is required")
    s = str(state).strip().upper()
    s = STATE_NAME_MAP.get(s, s)
    if s not in SUPPORTED_STATES:
        raise ProfileValidationError(
            f"State '{state}' is not supported. AidRadar currently covers CA, TX, NY, and FL."
        )
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

    # State
    cleaned["state"] = _normalize_state(profile.get("state"))

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
        cleaned_children.append({
            "age": int(_coerce_number(child.get("age", 5), f"children[{i}].age", 0, 17)),
        })
    cleaned["children"] = cleaned_children

    # Household sanity check
    total = len(cleaned_adults) + len(cleaned_children)
    if total == 0:
        raise ProfileValidationError("Household must have at least 1 member.")
    if total > 20:
        raise ProfileValidationError("Household size exceeds maximum of 20.")

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
