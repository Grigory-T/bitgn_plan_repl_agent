from pathlib import Path
import re
from typing import Literal

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


def _infer_catalog_refs(text: str) -> list[str]:
    refs: list[str] = []
    for ref in re.findall(r"/proc/catalog/[A-Za-z0-9_/-]+/[A-Z0-9-]+\.json|/proc/catalog/[A-Z0-9-]+\.json", text):
        if ref not in refs:
            refs.append(ref)
    for sku in re.findall(r"\b[A-Z]{3}-[A-Z0-9]{8}\b", text):
        ref = f"/proc/catalog/{sku}.json"
        if not any(existing.endswith(f"/{sku}.json") for existing in refs):
            refs.append(ref)
    return refs


def _ensure_yes_no_token(task: str, message: str, evidence: str) -> str:
    if "<YES>" in message or "<NO>" in message:
        return message
    if not task.strip().lower().startswith("do you have"):
        return message

    message_lower = message.strip().lower()
    evidence_lower = evidence.lower()
    no_markers = (
        message_lower.startswith("no")
        or "couldn't find" in message_lower
        or "could not find" in message_lower
        or "cannot confirm" in message_lower
        or "no match" in evidence_lower
        or "zero results" in evidence_lower
        or "does not exist" in evidence_lower
        or "no '" in evidence_lower
    )
    yes_markers = (
        message_lower.startswith("yes")
        or "does include" in evidence_lower
        or "there is" in evidence_lower
        or "exists in the catalogue" in evidence_lower
    )
    if no_markers:
        return "<NO> " + message.lstrip()
    if yes_markers:
        return "<YES> " + message.lstrip()
    return message


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
    evidence_text = "\n".join([agent_answer, summarized_steps, decision.message])
    decision.message = _ensure_yes_no_token(task, decision.message, evidence_text)
    cleaned_refs: list[str] = []
    for ref in [*decision.refs, *_infer_catalog_refs(evidence_text)]:
        cleaned = (ref or "").strip()
        if cleaned and cleaned not in cleaned_refs:
            cleaned_refs.append(cleaned)
    decision.refs = cleaned_refs
    return decision
