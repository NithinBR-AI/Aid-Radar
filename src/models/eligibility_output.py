"""
Pydantic schema for Eligibility Agent output.

Validates the JSON the Eligibility Agent produces before it reaches the
Recommendation Agent. If validation fails, the pipeline returns a clear error
instead of the Recommendation Agent silently working with malformed data.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class HouseholdSummary(BaseModel):
    state: str
    household_size: int | None = None
    monthly_income: float | None = None


class EligibleProgram(BaseModel):
    program_id: str
    program_name: str
    eligible: bool
    estimated_monthly_benefit: float | None = None
    estimated_annual_benefit: float | None = None
    application_url: str | None = None
    required_documents: list[str] = Field(default_factory=list)
    cascading_benefits: list[str] = Field(default_factory=list)


class IneligibleProgram(BaseModel):
    program_id: str
    reason: str | None = None


class ErrorProgram(BaseModel):
    program_id: str
    reason: str | None = None


class EligibilityOutput(BaseModel):
    household_summary: HouseholdSummary
    eligible_programs: list[EligibleProgram] = Field(default_factory=list)
    ineligible_programs: list[IneligibleProgram] = Field(default_factory=list)
    error_programs: list[ErrorProgram] = Field(default_factory=list)
    total_estimated_monthly_benefit: float | None = None
    total_estimated_annual_benefit: float | None = None

    @model_validator(mode="before")
    @classmethod
    def allow_extra_fields(cls, data: Any) -> Any:
        # LLMs sometimes add extra fields — ignore them rather than failing
        if isinstance(data, dict):
            known = {f for f in cls.model_fields}
            return {k: v for k, v in data.items() if k in known}
        return data


def parse_eligibility_output(text: str) -> EligibilityOutput | None:
    """Extract and validate EligibilityOutput from agent text.

    Returns None if no valid JSON found or validation fails — callers must
    handle None and fall back to passing raw eligibility_text downstream.
    """
    import json
    import re
    import logging

    logger = logging.getLogger(__name__)

    # Extract fenced JSON block
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    raw = match.group(1) if match else None

    if not raw:
        # Fallback: find outermost balanced brace
        start = text.find("{")
        if start == -1:
            return None
        depth = 0
        for i, ch in enumerate(text[start:], start=start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    raw = text[start:i + 1]
                    break

    if not raw:
        return None

    try:
        data = json.loads(raw)
        return EligibilityOutput.model_validate(data)
    except Exception as e:
        logger.warning("parse_eligibility_output validation failed: %s", e)
        return None
