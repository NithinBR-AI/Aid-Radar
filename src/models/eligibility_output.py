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

    Tries every JSON object in the text and returns the first one that
    validates against EligibilityOutput. This handles mixed prose+JSON
    output where the schema object may not be the first brace found.

    Returns None if no valid JSON found or validation fails.
    """
    import json
    import re
    import logging

    logger = logging.getLogger(__name__)

    if not text:
        return None

    # Collect candidate JSON strings — fenced blocks first, then all balanced objects
    candidates: list[str] = []

    for m in re.finditer(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL):
        candidates.append(m.group(1))

    # Walk the full text and extract every top-level balanced JSON object
    i = 0
    while i < len(text):
        if text[i] == "{":
            depth = 0
            for j in range(i, len(text)):
                if text[j] == "{":
                    depth += 1
                elif text[j] == "}":
                    depth -= 1
                    if depth == 0:
                        candidates.append(text[i:j + 1])
                        i = j
                        break
        i += 1

    # Try each candidate — return first that validates as EligibilityOutput
    for raw in candidates:
        try:
            data = json.loads(raw)
            if not isinstance(data, dict) or "household_summary" not in data:
                continue
            return EligibilityOutput.model_validate(data)
        except Exception:
            continue

    logger.warning("parse_eligibility_output: no valid EligibilityOutput found in %d chars", len(text))
    return None
