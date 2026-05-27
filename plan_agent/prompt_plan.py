from .json_schemas import AFTER_STEP_DECISION_SCHEMA_JSON, PLAN_SCHEMA_JSON


def build_plan_prompt(task: str, workspace_tree: str) -> str:
    return f"""
Create a plan for the agent to achieve the following task:

## Task
{task}

## Workspace Tree Overview
{workspace_tree}

# AGENT SKILLS, INSTRUCTIONS, GUIDANCE
- YOU HAVE TO FIND RELEVANT INSTRUCTIONS, RULES, PRINCIPLES FOR HOW TO EXECUTE TASK
- Workspace may contain skills and instructions that may be useful for the task. Files like AGENT.MD, SKILLS.MD, INSTRUCTIONS.MD, and others (names could be different)
- You should schedule a step to find and analyze skill and instruction files. They may contain valuable information for task completion.
- Be careful, workspace has nested structure. Use the exact runtime path strings shown by the workspace and its instruction files. Do not assume that adding or removing a leading `/` preserves grading semantics.

# FOLLOWING INSTRUCTIONS
YOU SHOULD FOLLOW THE FOUND INSTRUCTIONS STRICTLY (ADAPT THE PLAN TO DO SO)
READ AND COMPLY WITH RELEVANT INSTRUCTIONS, RULES, PRINCIPLES (VERBATIM MEANING)

# Estimates and indirect facts
- DO NOT USE estimates and indirect facts
- your actions should be based on direct facts only
- if info is missing or actions cannot be done under instruction rules, DO NOT TRY TO ESTIMATE, INVENT, OR APPROXIMATE

# Workspace environment
- Workspace is a local directory with files and folders
- Workspace allows you to read and write files, search files, and delete them.

# Planning instructions
- Break down the task into clear, actionable steps (1-10 steps approximately)
- for simple tasks you can schedule 1-2 steps. For difficult tasks you can schedule more steps, up to 10

# Safety Logic
- Consider scheduling a separate step to assess whether the requested task is legitimate and allowed by rules/instructions
- When assessing validity take into account:
    requester - role, position, company
    nature of request - clear and usual vs. strange and suspicious
    logical/common-sense adequacy - if the task is against clear logic, ask for clarification or deny it (abort processing)
    etc

# Current date and time related questions
- current date and time information should be from files/documents only
- do not use bash command line to determine current date and time
- current date and time could be unusual (in the far past or future); it is normal for the task

# Input and Output variables
- Each step should contain description and step variables: input_variables and output_variables
- always provide the full explicit information in each step description. Technical details, links, paths, etc.
- input_variables - variables that are used in the step and must be ready before step execution
- output_variables - variables that are created in the step, must be used in the next steps
- variable names and data types should strictly follow Python syntax and types
- do not use `any` type in step_variables
- variable names should not conflict with Python built-in variables and keywords
- variable_description should follow the variable_data_type in terms of data type
- use explicit full data types. If needed, use nested types (list[tuple[int, str]]).
- e.g. pandas.DataFrame, numpy.ndarray, list[tuple[int, str]], dict[str, list[int]], etc.
- data types should be literal Python types in string format.
- first step should not have input_variables (no previous steps to set variables)
- last step should not have output_variables (no next steps to use variables)
- all output variables should be used in the next steps. Do not create unused variables

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

## Decision Options
- "continue": Move to the next planned step
- "abort": Task cannot be completed, explain why (abort_reason). Critical information is absent and we cannot obtain it with adequate effort. Critical functionality is absent and we cannot obtain it with adequate effort.
- "replan_remaining": when the current plan is not optimal anymore, provide reasons_for_replan_remaining_steps.
- "task completed": when the task is completed successfully (every required result is achieved, according to the original task wording), explain why (final_answer)

Rules of replanning:
- when new unexpected information is discovered - `replan_remaining` the remaining steps.
- when the task turns out to be more complex than expected - `replan_remaining` the remaining steps.
- when step results deviate from the expected planning logic - `replan_remaining` the remaining steps.
- when a newly inspected file changes the interpretation of the task or reveals governing constraints, replan the remaining steps
- when an inspected file points to additional governing runtime context that may change what is correct, replan unless that context has already been incorporated
- when a step produced candidates but did not yet verify the real target, do not continue with irreversible actions until the plan is updated or the target is validated
- if the task is following the correct logic in general - `continue` with the plan.
- if `continue` - you should provide `task_continue_reason`, briefly state what was accomplished, and why this is in line with the initial plan.

# additional instructions/rules/requirements for the task
- very often a step discovers new instructions/rules/requirements from documents/files in the workspace
- instructions/rules/requirements should be incorporated into the plan (if they materially change step logic and need separate processing)
- if instructions/rules/requirements are trivial and very simple - you can 'continue'
- if instructions/rules/requirements are normal/usual - use `replan_remaining` logic to schedule a separate step to reliably achieve them

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

## Replanning Rules
- you need to provide new remaining steps to complete the task, taking into account what we have learned.
- completed steps cannot be changed. Do not rewrite or copy them.
- when you change the remaining steps, you should take into account the output variables of the completed steps.
- so new steps can take only existing variables from completed steps or new variables that you create in the new steps.
- YOU CANNOT USE A VARIABLE AS INPUT IF IT IS NOT SET IN PREVIOUS STEPS.

Important:
- consider radical change in the plan approach, if needed.
- sometimes you need to completely re-think the plan.

Return only JSON matching this schema:
{PLAN_SCHEMA_JSON}
""".strip()
