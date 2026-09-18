from __future__ import annotations

import math
import os
import re
from typing import Any

from pydantic import BaseModel, Field


class ExtractedScalar(BaseModel):
    value: float | None = Field(default=None, description="Numeric value explicitly present in the user text")
    evidence: str = Field(default="", description="Exact source span copied from the user text")


class RequirementStructuredExtraction(BaseModel):
    dimensionless_groups: dict[str, ExtractedScalar] = Field(default_factory=dict)


DIMENSIONLESS_ALIASES: dict[str, tuple[str, ...]] = {
    "beta": ("beta", "β"),
    "De": ("de", "deborah", "deborah number", "德博拉"),
    "Wi": ("wi", "weissenberg", "weissenberg number", "魏森伯格"),
    "Re": ("re", "reynolds", "reynolds number", "雷诺"),
}

_ALIAS_TO_CANONICAL = {
    alias.casefold(): canonical
    for canonical, aliases in DIMENSIONLESS_ALIASES.items()
    for alias in aliases
}


def llm_extractor_enabled() -> bool:
    return os.getenv("FOAMAGENT_ENABLE_LLM_STRUCTURED_EXTRACTOR", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "").casefold())


def _canonical_group_name(name: str) -> str | None:
    lowered = str(name or "").casefold().strip()
    if lowered in _ALIAS_TO_CANONICAL:
        return _ALIAS_TO_CANONICAL[lowered]
    if lowered in {key.casefold(): key for key in DIMENSIONLESS_ALIASES}:
        return {key.casefold(): key for key in DIMENSIONLESS_ALIASES}[lowered]
    return None


def _evidence_is_grounded(user_requirement: str, group: str, evidence: str) -> bool:
    evidence = str(evidence or "").strip()
    if not evidence:
        return False
    if _compact(evidence) not in _compact(user_requirement):
        return False
    lowered = evidence.casefold()
    return any(alias.casefold() in lowered for alias in DIMENSIONLESS_ALIASES[group])


def merge_llm_dimensionless_groups(
    user_requirement: str,
    deterministic_groups: dict[str, float],
    extraction: RequirementStructuredExtraction,
    *,
    tolerance: float = 1e-9,
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    """Merge LLM-extracted scalar candidates only after deterministic grounding checks.

    The LLM is an extractor, not the routing authority: values are accepted only
    when the model supplies an exact evidence span from the user text and does
    not conflict with an already parsed deterministic value.
    """
    merged = dict(deterministic_groups)
    audit: list[dict[str, Any]] = []
    for raw_name, scalar in (extraction.dimensionless_groups or {}).items():
        group = _canonical_group_name(raw_name)
        if group is None:
            audit.append({"field": raw_name, "status": "rejected", "reason": "unsupported_dimensionless_group"})
            continue
        value = scalar.value
        if value is None or not math.isfinite(float(value)):
            audit.append({"field": group, "status": "rejected", "reason": "non_numeric_value"})
            continue
        if not _evidence_is_grounded(user_requirement, group, scalar.evidence):
            audit.append({"field": group, "status": "rejected", "reason": "evidence_not_grounded"})
            continue
        numeric_value = float(value)
        if group in merged and abs(float(merged[group]) - numeric_value) > tolerance:
            audit.append(
                {
                    "field": group,
                    "status": "rejected",
                    "reason": "conflicts_with_deterministic_value",
                    "deterministic_value": merged[group],
                    "llm_value": numeric_value,
                    "evidence": scalar.evidence,
                }
            )
            continue
        if group not in merged:
            merged[group] = numeric_value
            audit.append({"field": group, "status": "accepted", "value": numeric_value, "evidence": scalar.evidence})
    return merged, audit


def extract_requirement_with_llm(user_requirement: str, *, llm: Any | None = None) -> RequirementStructuredExtraction | None:
    """Best-effort structured extraction. Returns None if LLM is unavailable."""
    if llm is None:
        try:
            from services import global_llm_service as llm  # lazy import; may depend on runtime config
        except Exception:
            return None

    system_prompt = (
        "You extract CFD requirement fields. Return only fields explicitly present in the user text. "
        "Do not infer, estimate, or choose solvers/templates. For every value, copy an exact evidence span "
        "from the user text. If absent, omit the field."
    )
    user_prompt = (
        "Extract only dimensionless groups beta, De, Wi, Re from this requirement. "
        "Support formula forms such as 'De: lambda*U/L = 1' or words such as 'Deborah number is one'.\n\n"
        f"Requirement:\n{user_requirement}"
    )
    try:
        return llm.invoke(
            user_prompt,
            system_prompt,
            pydantic_obj=RequirementStructuredExtraction,
            max_retries=0,
        )
    except Exception:
        return None
