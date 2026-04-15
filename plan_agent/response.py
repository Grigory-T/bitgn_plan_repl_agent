from pathlib import Path

from pydantic import BaseModel

from .prompt_response import build_response_decision_prompt
from .utils import llm_structured, LLM_MODEL_RESPONSE


class ResponseDecision(BaseModel):
    message: str
    reasoning: str


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
    return llm_structured(prompt, ResponseDecision, model=LLM_MODEL_RESPONSE)
