import json
import os
from datetime import datetime
from pathlib import Path
import re

from .plan import Plan


def _sanitize_log_segment(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return cleaned.strip("._-") or "task"


def _init_log_dir(task_id: str | None = None, batch_id: str | None = None) -> Path:
    log_root = os.getenv("PLAN_REPL_LOG_ROOT")
    if log_root:
        base = Path(log_root)
        if batch_id:
            base = base / _sanitize_log_segment(batch_id)
    else:
        batch_segment = _sanitize_log_segment(batch_id) if batch_id else datetime.now().strftime("%Y%m%d_%H%M%S")
        base = Path(__file__).resolve().parent.parent / "logs" / batch_segment
    log_dir = base / _sanitize_log_segment(task_id) if task_id else base
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


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
