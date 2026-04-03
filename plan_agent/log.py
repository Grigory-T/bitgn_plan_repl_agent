import json
from datetime import datetime
from pathlib import Path

from .plan import Plan


def _init_log_dir() -> Path:
    base = Path(__file__).resolve().parent.parent / "logs" / datetime.now().strftime("%Y%m%d_%H%M%S")
    base.mkdir(parents=True, exist_ok=True)
    return base


def _append_log(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as log_file:
        log_file.write(content.rstrip() + "\n\n")


def _append_step_log(path: Path, role: str, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as log_file:
        separator = "=" * 80
        log_file.write(f"\n{separator}\n[{role.upper()}]\n{separator}\n{content}\n\n")


def _append_reasoning(path: Path, reasoning: str) -> None:
    if not reasoning:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        separator = "~" * 80
        f.write(reasoning + f"\n\n{separator}\n\n")


def _write_log(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as log_file:
        log_file.write(content.rstrip() + "\n")


def _format_refs(refs: list[str], title: str = "Reported Refs:") -> str:
    lines = [title]
    if refs:
        lines.extend(f"- {ref}" for ref in refs)
    else:
        lines.append("(none)")
    return "\n".join(lines)


def _format_preflight(
    *,
    should_proceed: bool,
    outcome: str,
    explanation: str,
    notes: list[str],
    denial_message: str | None,
) -> str:
    lines = [
        "Preflight",
        f"Status: {'PASSED' if should_proceed else 'DENIED'}",
        f"Outcome: {outcome}",
        f"Explanation: {explanation}",
        "",
        "Notes:",
    ]
    if notes:
        lines.extend(f"- {note}" for note in notes)
    else:
        lines.append("(none)")

    if denial_message:
        lines.extend([
            "",
            "Denial Message:",
            denial_message,
        ])

    return "\n".join(lines)


def _format_plan(plan: Plan, start_step: int = 1) -> str:
    lines = []
    separator = "-" * 80
    for idx, step in enumerate(plan.steps, start_step):
        lines.append(f"\n{separator}")
        lines.append(f"Step {idx}: {step.step_description}")
        lines.append(separator)
        
        def _serialize_vars(vars_list):
            if isinstance(vars_list, dict):
                return json.dumps(vars_list, indent=4, ensure_ascii=False)
            return json.dumps([v.model_dump() for v in vars_list], indent=4, ensure_ascii=False)
        
        lines.append(f"input_variables: {_serialize_vars(step.input_variables)}")
        lines.append(f"output_variables: {_serialize_vars(step.output_variables)}")
    return "\n".join(lines)
