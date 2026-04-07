from typing import Literal
from pathlib import Path

from pydantic import BaseModel, Field

from .prompt_response import build_response_decision_prompt
from .utils import llm_structured, LLM_MODEL_RESPONSE


class ResponseDecision(BaseModel):
    message: str
    outcome: Literal[
        "OUTCOME_OK",
        "OUTCOME_DENIED_SECURITY",
        "OUTCOME_NONE_CLARIFICATION",
        "OUTCOME_NONE_UNSUPPORTED",
        "OUTCOME_ERR_INTERNAL",
    ]
    refs: list[str] = Field(default_factory=list)
    should_submit_to_bitgn: bool
    reasoning: str


def _clean_ref(path: str) -> str:
    return (path or "").strip()


def decide_response(
    task: str,
    agent_answer: str,
    step_results: list[str] | None = None,
    log_dir: str | None = None,
) -> ResponseDecision:
    summarized_steps = "\n".join(f"- {result}" for result in (step_results or [])) or "(none)"
    prompt = build_response_decision_prompt(
        task=task,
        agent_answer=agent_answer,
        step_results=summarized_steps,
    )
    if log_dir:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        (log_path / "response_prompt.txt").write_text(prompt.rstrip() + "\n", encoding="utf-8")
    decision = llm_structured(prompt, ResponseDecision, model=LLM_MODEL_RESPONSE)
    decision.should_submit_to_bitgn = True
    cleaned_refs: list[str] = []
    for ref in decision.refs:
        cleaned = _clean_ref(ref)
        if cleaned and cleaned not in cleaned_refs:
            cleaned_refs.append(cleaned)
    decision.refs = cleaned_refs

    return decision
