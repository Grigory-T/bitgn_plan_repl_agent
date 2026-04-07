import os
from typing import Literal

from pydantic import BaseModel, Field

from .prompt_preflight import build_preflight_prompt
from .utils import LLM_MODEL_PLAN, llm_structured


PreflightOutcome = Literal[
    "proceed",
    "proceed_with_caution",
    "deny_needs_clarification",
    "deny_prompt_injection",
    "deny_destructive_or_conflicting_request",
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


def preflight_check(task: str) -> PreflightDecision:
    if os.getenv("BITGN_DEBUG_PREFLIGHT_DENY") == "1":
        return PreflightDecision(
            should_proceed=False,
            outcome="deny_destructive_or_conflicting_request",
            explanation="Forced preflight denial for debug logging mode.",
            notes=["Debug mode enabled via BITGN_DEBUG_PREFLIGHT_DENY=1."],
            denial_message="Forced preflight denial for debug logging mode.",
        )

    prompt = build_preflight_prompt(task)
    result = llm_structured(prompt, PreflightAssessment, model=LLM_MODEL_PLAN)

    if result.outcome == "deny_prompt_injection" and result.confidence >= 4:
        return PreflightDecision(
            should_proceed=False,
            outcome=result.outcome,
            explanation=result.explanation,
            notes=result.notes,
            denial_message="Task text contains prompt-injection or instruction-override content.",
        )

    if result.outcome == "deny_destructive_or_conflicting_request" and result.confidence >= 4:
        return PreflightDecision(
            should_proceed=False,
            outcome=result.outcome,
            explanation=result.explanation,
            notes=result.notes,
            denial_message="Task directly conflicts with the agent's operating rules.",
        )

    if result.outcome == "deny_needs_clarification" and result.confidence >= 4:
        return PreflightDecision(
            should_proceed=False,
            outcome=result.outcome,
            explanation=result.explanation,
            notes=result.notes,
            denial_message="Task is incomplete or too vague to execute reliably. Please clarify the requested action.",
        )

    return PreflightDecision(
        should_proceed=True,
        outcome=result.outcome,
        explanation=result.explanation,
        notes=result.notes,
    )
