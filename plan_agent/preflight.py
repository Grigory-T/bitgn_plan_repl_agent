import os
import re
from typing import Literal

from pydantic import BaseModel, Field

from .prompt_preflight import build_preflight_prompt
from .utils import LLM_MODEL_PLAN, llm_structured


PreflightOutcome = Literal[
    "proceed",
    "proceed_with_caution",
    "deny_needs_clarification",
    "deny_prompt_injection",
    "deny_forbidden_or_conflicting_request",
]


class PreflightAssessment(BaseModel):
    outcome: PreflightOutcome = Field(..., description="High-level preflight outcome")
    explanation: str = Field(..., description="Short explanation of the decision")
    notes: list[str] = Field(default_factory=list, description="Short practical notes for later planning")
    confidence: int = Field(..., ge=1, le=5, description="Confidence level 1-5")


class PreflightDecision(BaseModel):
    should_proceed: bool
    outcome: PreflightOutcome
    explanation: str
    notes: list[str] = Field(default_factory=list)
    denial_message: str | None = None
    bitgn_outcome: str | None = None


_PROMPT_INJECTION_PATTERNS = [
    r"\bignore (all )?(previous|prior|above|system|developer) instructions\b",
    r"\bdisregard (all )?(previous|prior|above|system|developer) instructions\b",
    r"\boverride (the )?(system|developer|safety|policy) (prompt|instructions|rules)\b",
    r"\breveal (the )?(system|developer|hidden) (prompt|instructions|message)\b",
    r"\bshow (me )?(the )?(system|developer|hidden) prompt\b",
    r"\bdisable (safety|policy|guardrails|filters)\b",
]

_FORBIDDEN_PATTERNS = [
    r"\bbypass (checkout|payment|fraud|risk|policy|authorization|approval)\b",
    r"\bforce (a )?(refund|discount|coupon|credit|replacement|approval)\b",
    r"\b(forge|fabricate|fake|alter) (logs|evidence|order history|support records|warehouse evidence)\b",
    r"\bhide (logs|evidence|audit|audit trail|order history|support records)\b",
    r"\bexfiltrate\b.*\b(customer|payment|account|private|personal)\b",
]


def _short_error(exc: Exception, limit: int = 400) -> str:
    text = " ".join(str(exc).split())
    return text if len(text) <= limit else text[:limit].rstrip() + "..."


def _pattern_matches(patterns: list[str], text: str) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def _deterministic_preflight(task: str) -> PreflightDecision | None:
    normalized = " ".join(task.strip().split())
    if not normalized:
        return PreflightDecision(
            should_proceed=False,
            outcome="deny_needs_clarification",
            explanation="Task text is empty.",
            denial_message="Task is empty. Please clarify the requested action.",
            bitgn_outcome="OUTCOME_NONE_CLARIFICATION",
        )

    if _pattern_matches(_PROMPT_INJECTION_PATTERNS, normalized):
        return PreflightDecision(
            should_proceed=False,
            outcome="deny_prompt_injection",
            explanation="Task text contains an explicit instruction-override or prompt-reveal request.",
            denial_message="Task text contains prompt-injection or instruction-override content.",
            bitgn_outcome="OUTCOME_DENIED_SECURITY",
        )

    if _pattern_matches(_FORBIDDEN_PATTERNS, normalized):
        return PreflightDecision(
            should_proceed=False,
            outcome="deny_forbidden_or_conflicting_request",
            explanation="Task text directly requests bypassing policy/control boundaries or manipulating evidence.",
            denial_message="Task directly conflicts with ECOM policy, trust, privacy, or evidence-integrity boundaries.",
            bitgn_outcome="OUTCOME_DENIED_SECURITY",
        )

    return None


def preflight_check(task: str) -> PreflightDecision:
    if os.getenv("BITGN_DEBUG_PREFLIGHT_DENY") == "1":
        return PreflightDecision(
            should_proceed=False,
            outcome="deny_forbidden_or_conflicting_request",
            explanation="Forced preflight denial for debug logging mode.",
            notes=["Debug mode enabled via BITGN_DEBUG_PREFLIGHT_DENY=1."],
            denial_message="Forced preflight denial for debug logging mode.",
            bitgn_outcome="OUTCOME_DENIED_SECURITY",
        )

    deterministic_decision = _deterministic_preflight(task)
    if deterministic_decision is not None:
        return deterministic_decision

    try:
        result = llm_structured(build_preflight_prompt(task), PreflightAssessment, model=LLM_MODEL_PLAN)
    except Exception as exc:
        return PreflightDecision(
            should_proceed=True,
            outcome="proceed_with_caution",
            explanation=f"Preflight model failed; proceeding with normal planning: {_short_error(exc)}",
            notes=["Preflight is fail-open to avoid blocking normal ECOM task execution."],
        )

    if result.outcome.startswith("deny_"):
        return PreflightDecision(
            should_proceed=True,
            outcome="proceed_with_caution",
            explanation=(
                f"LLM preflight suggested {result.outcome}, but ECOM preflight only blocks deterministic "
                f"early-deny patterns. Original explanation: {result.explanation}"
            ),
            notes=[
                *result.notes,
                "Proceeding because normal ECOM task details should be verified from runtime evidence and policy.",
            ],
        )

    return PreflightDecision(
        should_proceed=True,
        outcome=result.outcome,
        explanation=result.explanation,
        notes=result.notes,
    )
