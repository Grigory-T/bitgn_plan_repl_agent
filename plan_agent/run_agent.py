from .plan import (
    AfterStepDecision,
    Plan,
    PlanStep,
    create_plan,
    make_after_step_decision,
    replan_remaining,
)
from .run_step import run_step
from .executor import execute_python
from .preflight import preflight_check
from .log import _init_log_dir, _append_log, _format_plan, _format_preflight, _write_log


MAX_TOTAL_STEPS = 30


def _finalize_run(log_dir, result: str, completed_steps: list[tuple[PlanStep, str]]) -> tuple[str, str, list[str]]:
    step_results = [step_result for _, step_result in completed_steps]
    _write_log(log_dir / "agent_result.txt", result)
    return result, str(log_dir), step_results


def run_agent(task: str, task_id: str | None = None, batch_id: str | None = None) -> tuple[str, str, list[str]]:
    log_dir = _init_log_dir(task_id=task_id, batch_id=batch_id)
    preflight = preflight_check(task)
    _write_log(
        log_dir / "preflight.txt",
        _format_preflight(
            should_proceed=preflight.should_proceed,
            outcome=preflight.outcome,
            explanation=preflight.explanation,
            notes=preflight.notes,
            denial_message=preflight.denial_message,
        ),
    )
    if not preflight.should_proceed:
        result = f"Request denied at preflight: {preflight.denial_message or preflight.explanation}"
        return _finalize_run(log_dir, result, [])

    plan, plan_warnings = create_plan(task)
    remaining_steps: list[PlanStep] = list(plan.steps)
    completed_steps: list[tuple[PlanStep, str]] = []
    initial_plan_text = "Initial plan:\n" + _format_plan(plan)
    if plan_warnings:
        initial_plan_text += "\n\nPlan validation warnings:\n" + "\n".join(plan_warnings)
    _append_log(log_dir / "plan.txt", initial_plan_text)

    for _ in range(MAX_TOTAL_STEPS):
        if not remaining_steps:
            break

        current_step = remaining_steps.pop(0)
        step_number = len(completed_steps) + 1
        
        execute_python("final_answer = ''")

        step_result = run_step(
            task=task,
            current_step=current_step,
            completed_steps=completed_steps,
            log_dir=log_dir,
            step_index=step_number,
        )
        completed_steps.append((current_step, step_result))

        decision: AfterStepDecision = make_after_step_decision(
            task=task,
            completed_steps=completed_steps,
            remaining_steps=remaining_steps,
        )
        _append_log(
            log_dir / "decisions.txt",
            f"Decision after step {step_number}:\n{decision.model_dump_json(indent=2)}",
        )

        if decision.next_action == "abort":
            result = decision.abort_reason or "Aborted by decision"
            return _finalize_run(log_dir, result, completed_steps)

        if decision.next_action == 'task_completed':
            result = decision.task_completed_reason or completed_steps[-1][1]
            return _finalize_run(log_dir, result, completed_steps)

        if decision.next_action == "replan_remaining_steps":
            plan, plan_warnings = replan_remaining(
                task=task,
                completed_steps=completed_steps,
                remaining_steps=remaining_steps,
                after_step_decision=decision,
            )
            remaining_steps = list(plan.steps)
            replan_text = f"Replan after step {step_number}:\n" + _format_plan(plan, start_step=step_number + 1)
            if plan_warnings:
                replan_text += "\n\nPlan validation warnings:\n" + "\n".join(plan_warnings)
            _append_log(
                log_dir / "plan.txt",
                replan_text,
            )

    if remaining_steps:
        result = "Stopped: exceeded max total steps."
        return _finalize_run(log_dir, result, completed_steps)

    result = completed_steps[-1][1]
    return _finalize_run(log_dir, result, completed_steps)
