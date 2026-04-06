import json
from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from .utils import llm_structured, LLM_MODEL_PLAN, LLM_MODEL_DECISION, LLM_MODEL_REPLAN
from .prompt_plan import PLAN_PROMPT, DECISION_PROMPT, REPLAN_REMAINING_PROMPT
import bitgn_runtime


PLAN_TREE_MAX_CHARS = 4000


class StepVariable(BaseModel):
    variable_name: str = Field(..., description='Name of the python variable in global scope')
    variable_description: str = Field(..., description='Description of the python variable, in natural language')
    variable_data_type: str = Field(..., description='Python type of the variable (python typing). Allowed values: str, int, float, bool, list, dict, tuple, set. Use nesdted dtypes e.g. list[tuple[int, str]]. Do not use `any` type.')


class PlanStep(BaseModel):
    
    input_variables: list[StepVariable] = Field(
        default_factory=list,
        description="Input variables and their dtypes",
    )

    step_description: str = Field(..., description="What this step should accomplish using input variables. THe result of the step should be stored in output variables. Include all relevant information from the task, related to this step.")

    output_variables: list[StepVariable] = Field(
        default_factory=list,
        description="Output variables and their dtypes",
    )


class Plan(BaseModel):
    steps: List[PlanStep] = Field(default_factory=list, description="List of steps to execute")


class AfterStepDecision(BaseModel):
    next_action: Literal["continue", "abort", "replan_remaining_steps", "task_completed"] = Field(
        ..., description="What to do next"
    )
    abort_reason: Optional[str] = Field(None, description="Why task cannot be completed (for `abort` decision)")
    reasons_for_replan_remaining_steps: Optional[str] = Field(None, description="Reason for replanning remaining steps (for `replan_remaining_steps` decision)")
    task_completed_reason: Optional[str] = Field(None, description="Reason for task completion (for `task_completed` decision)")
    task_continue_reason: Optional[str] = Field(None, description="Reason for continuing the task (for `continue` decision)")


def _workspace_tree_overview() -> str:
    try:
        tree_text = bitgn_runtime.tree("/")
    except Exception as exc:
        return f"(workspace overview unavailable: {exc})"

    if len(tree_text) <= PLAN_TREE_MAX_CHARS:
        return tree_text
    return tree_text[:PLAN_TREE_MAX_CHARS].rstrip() + "\n... [truncated]"


def create_plan(task: str) -> tuple[Plan, list[str]]:
    prompt = PLAN_PROMPT.format(task=task, workspace_tree=_workspace_tree_overview())
    plan = llm_structured(prompt, Plan, model=LLM_MODEL_PLAN)
    warnings = check_plan(plan)
    return plan, warnings

def make_after_step_decision(
    task: str,
    completed_steps: List[tuple[PlanStep, str]],
    remaining_steps: List[PlanStep],
) -> AfterStepDecision:
    prompt = DECISION_PROMPT.format(
        task=task,
        completed_steps=format_completed_steps(completed_steps),
        remaining_steps=format_remaining_steps(remaining_steps, start_step=len(completed_steps) + 1),
    )
    return llm_structured(prompt, AfterStepDecision, model=LLM_MODEL_DECISION)


def replan_remaining(
    task: str,
    completed_steps: List[tuple[PlanStep, str]],
    remaining_steps: List[PlanStep],
    after_step_decision: AfterStepDecision,
) -> tuple[Plan, list[str]]:
    prompt = REPLAN_REMAINING_PROMPT.format(
        task=task,
        completed_steps=format_completed_steps(completed_steps),
        remaining_steps=format_remaining_steps(remaining_steps, start_step=len(completed_steps) + 1),
        reasons_for_replan_remaining_steps=after_step_decision.reasons_for_replan_remaining_steps,
    )
    plan = llm_structured(prompt, Plan, model=LLM_MODEL_REPLAN)
    warnings = check_plan(plan)
    return plan, warnings


def format_completed_steps(completed_steps: List[tuple[PlanStep, str]]) -> str:
    lines = []
    for i, (step, result) in enumerate(completed_steps, 1):
        lines.append(f"Step {i}: {step.step_description}")
        
        if step.input_variables:
            input_vars = ", ".join(
                f"{v.variable_name} ({v.variable_data_type})"
                for v in step.input_variables
            )
            lines.append(f"  Input variables: {input_vars}")
        
        if step.output_variables:
            output_vars = ", ".join(
                f"{v.variable_name} ({v.variable_data_type})"
                for v in step.output_variables
            )
            lines.append(f"  Output variables: {output_vars}")
        
        lines.append(f"  Result: {result}")
        lines.append("")  # Empty line between steps
    
    return "\n".join(lines).rstrip()


def format_remaining_steps(remaining_steps: List[PlanStep], start_step: int = 1) -> str:
    lines = []
    for i, step in enumerate(remaining_steps, start_step):
        lines.append(f"Step {i}: {step.step_description}")
        
        if step.input_variables:
            input_vars = ", ".join(
                f"{v.variable_name} ({v.variable_data_type})"
                for v in step.input_variables
            )
            lines.append(f"  Input variables: {input_vars}")
        
        if step.output_variables:
            output_vars = ", ".join(
                f"{v.variable_name} ({v.variable_data_type})"
                for v in step.output_variables
            )
            lines.append(f"  Output variables: {output_vars}")
        
        lines.append("")  # Empty line between steps
    
    return "\n".join(lines).rstrip()


def check_plan(plan: Plan) -> list[str]:
    """
    Validate plan consistency:
    1. Input variables must be outputs from previous steps (name + dtype match)
    2. First step should not have input variables
    3. Output variables should be consumed by subsequent steps (except last step)
    
    Logs warnings but does not interrupt execution.
    """
    if not plan.steps:
        return []
    
    warnings = []
    
    # Check 2: First step should not have input variables
    if plan.steps[0].input_variables:
        input_names = [v.variable_name for v in plan.steps[0].input_variables]
        warnings.append(
            f"⚠️ First step has input variables: {', '.join(input_names)}. "
            f"First step should not require inputs."
        )
    
    # Build a map of what each step outputs (name, dtype) tuples
    outputs_by_step = {}
    for idx, step in enumerate(plan.steps):
        outputs_by_step[idx] = {
            (v.variable_name, v.variable_data_type) 
            for v in step.output_variables
        }
    
    # Check 1: Input variables must be output by previous steps
    for idx, step in enumerate(plan.steps):
        if idx == 0:
            continue  # Skip first step
        
        for input_var in step.input_variables:
            found = False
            for prev_idx in range(idx):
                if (input_var.variable_name, input_var.variable_data_type) in outputs_by_step[prev_idx]:
                    found = True
                    break
            
            if not found:
                warnings.append(
                    f"⚠️ Step {idx + 1} requires input '{input_var.variable_name}' "
                    f"({input_var.variable_data_type}), but no previous step produces it."
                )
    
    # Check 3: Output variables should be consumed by subsequent steps
    for idx, step in enumerate(plan.steps):
        # Skip last step - its outputs are final results
        if idx == len(plan.steps) - 1:
            continue
        
        for output_var in step.output_variables:
            consumed = False
            for next_idx in range(idx + 1, len(plan.steps)):
                next_step = plan.steps[next_idx]
                for input_var in next_step.input_variables:
                    if (input_var.variable_name == output_var.variable_name and 
                        input_var.variable_data_type == output_var.variable_data_type):
                        consumed = True
                        break
                if consumed:
                    break
            
            if not consumed:
                warnings.append(
                    f"⚠️ Step {idx + 1} outputs '{output_var.variable_name}' "
                    f"({output_var.variable_data_type}), but it's not used by any subsequent step."
                )
    
    return warnings
