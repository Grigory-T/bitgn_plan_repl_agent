from .executor import execute_python
from .log import _append_log, _format_plan, _init_log_dir, _write_log
from .plan import (
    AfterStepDecision,
    PlanStep,
    create_plan,
    make_after_step_decision,
    replan_remaining,
)
from .progress import progress_event
from .run_step import run_step

MAX_TOTAL_STEPS = 30


def _finalize_run(
    log_dir, result: str, completed_steps: list[tuple[PlanStep, str]]
) -> tuple[str, str, list[str]]:
    step_results = [step_result for _, step_result in completed_steps]
    _write_log(log_dir / "agent_result.txt", result)
    return result, str(log_dir), step_results


def run_agent(
    task: str, task_id: str | None = None, batch_id: str | None = None
) -> tuple[str, str, list[str]]:
    log_dir = _init_log_dir(task_id=task_id, batch_id=batch_id)
    progress_event("planning_started")
    plan, plan_warnings = create_plan(task)
    progress_event(
        "planning_completed",
        planned_steps=len(plan.steps),
        warning_count=len(plan_warnings),
    )
    remaining_steps: list[PlanStep] = list(plan.steps)
    completed_steps: list[tuple[PlanStep, str]] = []
    initial_plan_text = "Initial plan:\n" + _format_plan(plan)
    if plan_warnings:
        initial_plan_text += "\n\nPlan validation warnings:\n" + "\n".join(
            plan_warnings
        )
    _append_log(log_dir / "plan.txt", initial_plan_text)

    for _ in range(MAX_TOTAL_STEPS):
        if not remaining_steps:
            break

        current_step = remaining_steps.pop(0)
        step_number = len(completed_steps) + 1
        progress_event(
            "step_started",
            step_number=step_number,
            remaining_steps=len(remaining_steps),
            input_count=len(current_step.input_variables),
            output_count=len(current_step.output_variables),
        )

        # Completion markers belong to one step only. Output variables remain
        # persistent, but stale status must never finalize the next step.
        execute_python("final_answer = ''\nstep_status = ''")

        step_result = run_step(
            task=task,
            current_step=current_step,
            completed_steps=completed_steps,
            log_dir=log_dir,
            step_index=step_number,
        )
        completed_steps.append((current_step, step_result))
        progress_event(
            "step_completed",
            step_number=step_number,
            result_chars=len(step_result),
        )

        progress_event("decision_started", after_step=step_number)
        decision: AfterStepDecision = make_after_step_decision(
            task=task,
            completed_steps=completed_steps,
            remaining_steps=remaining_steps,
        )
        progress_event(
            "decision_completed",
            after_step=step_number,
            action=decision.next_action,
            completed_steps=len(completed_steps),
            remaining_steps=len(remaining_steps),
        )
        _append_log(
            log_dir / "decisions.txt",
            f"Decision after step {step_number}:\n{decision.model_dump_json(indent=2)}",
        )

        if decision.next_action == "abort":
            result = decision.abort_reason or "Aborted by decision"
            return _finalize_run(log_dir, result, completed_steps)

        if decision.next_action == "task_completed":
            result = decision.task_completed_reason or completed_steps[-1][1]
            return _finalize_run(log_dir, result, completed_steps)

        if decision.next_action == "replan_remaining_steps":
            progress_event("replanning_started", after_step=step_number)
            plan, plan_warnings = replan_remaining(
                task=task,
                completed_steps=completed_steps,
                remaining_steps=remaining_steps,
                after_step_decision=decision,
            )
            remaining_steps = list(plan.steps)
            progress_event(
                "replanning_completed",
                after_step=step_number,
                planned_steps=len(remaining_steps),
                warning_count=len(plan_warnings),
            )
            replan_text = f"Replan after step {step_number}:\n" + _format_plan(
                plan, start_step=step_number + 1
            )
            if plan_warnings:
                replan_text += "\n\nPlan validation warnings:\n" + "\n".join(
                    plan_warnings
                )
            _append_log(
                log_dir / "plan.txt",
                replan_text,
            )

    if remaining_steps:
        result = "Stopped: exceeded max total steps."
        return _finalize_run(log_dir, result, completed_steps)

    result = completed_steps[-1][1]
    return _finalize_run(log_dir, result, completed_steps)
