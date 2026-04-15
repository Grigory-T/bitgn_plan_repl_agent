from .json_schemas import AFTER_STEP_DECISION_SCHEMA_JSON, PLAN_SCHEMA_JSON


def build_plan_prompt(task: str) -> str:
    return f"""
Create a short plan for the following task.

## Task
{task}

Rules:
- Keep the plan short and practical.
- Include an early step to inspect the working directory and any relevant instruction files.
- Use direct evidence from files.
- Do not invent missing facts.
- Use 1-6 steps.
- First step must not depend on input variables.
- Last step must not produce output variables.
- Output variables must be used later if they are created.

Return only JSON matching this schema:
{PLAN_SCHEMA_JSON}
""".strip()


def build_decision_prompt(task: str, completed_steps: str, remaining_steps: str) -> str:
    return f"""
You are evaluating the progress of a task execution and deciding what to do next.

## Original Task
{task}

## Completed Steps
{completed_steps}

## Remaining Steps in Plan
{remaining_steps}

Choose:
- `continue` if the current plan is still good
- `abort` if the task cannot be completed reliably
- `replan_remaining_steps` if new information changed the right approach
- `task_completed` if the original task is done

Replan when a new file, constraint, or discovery materially changes what the remaining steps should do.

Return only JSON matching this schema:
{AFTER_STEP_DECISION_SCHEMA_JSON}
""".strip()


def build_replan_remaining_prompt(
    task: str,
    completed_steps: str,
    remaining_steps: str,
    reasons_for_replan_remaining_steps: str,
) -> str:
    return f"""
You are replanning the remaining steps of a task based on new information.

## Original Task
{task}

## Completed Steps
{completed_steps}

## Old Remaining Steps in Plan (to be replaced)
{remaining_steps}

## Reasons for replanning remaining steps
{reasons_for_replan_remaining_steps}

Provide a better remaining plan based on what was learned.
Do not rewrite completed steps.
Only use input variables that already exist from completed steps or that are created by new remaining steps.

Return only JSON matching this schema:
{PLAN_SCHEMA_JSON}
""".strip()
