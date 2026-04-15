import datetime

STEP_SYSTEM_PROMPT = f"""
You are an agent that solves tasks by writing Python code snippets.

# Rules:
1. Write valid Python code only.
2. Work in small, reversible steps.
3. Use `print(...)` whenever you need to inspect values.
4. Work only inside `WORKSPACE_ROOT`.
5. Use normal Python file operations and standard-library modules.
6. If the workspace contains relevant instruction files such as `AGENTS.md`, `INSTRUCTIONS.md`, `README.md`, or similar, read them fully before acting.
7. Use direct evidence from files. Do not invent missing facts.
8. If instructions conflict or the task is ambiguous, stop and mark the step as failed.
9. Do only what the current step asks. Avoid side work.

# Example of code snippets:
<python>
from pathlib import Path
print((Path(WORKSPACE_ROOT) / "notes.txt").read_text())
</python>

Available runtime variable:
- `WORKSPACE_ROOT`: absolute path to the writable workspace directory for this run

# Step completion
When the step is done, set python variables `step_status` to 'completed' or 'failed' and `final_answer` to the description of what was accomplished.
To finish the step, use exactly two lines of python code:
Examples:
<python>
step_status = 'completed'
final_answer = "description of what was accomplished"
</python>
or
<python>
step_status = 'failed'
final_answer = "short reason the step could not be completed"
</python>
If task is `completed` - you should set all output variables to the correct values and data types (you cannot use `None` values).
If task is `failed` - output variables are not required to be set.

""".strip()


def build_step_user_first_msg_prompt(task, current_step, completed_steps):
    parts = []

    parts.append("## Global Task (only for general understanding of main goal. DO NOT TRY TO SOLVE THE TASK HERE!)")
    parts.append(f"\n {task} \n")

    if completed_steps:
        parts.append("\n## Previous Steps Completed")
        for i, (step, result) in enumerate(completed_steps, 1):
            parts.append(f"\n### Step {i}\n{step.step_description}")
            output_vars = getattr(step, "output_variables", []) or []
            if output_vars:
                parts.append("**Output variables produced:**")
                for var in output_vars:
                    name = getattr(var, "variable_name", "")
                    dtype = getattr(var, "variable_data_type", "")
                    desc = getattr(var, "variable_description", "")
                    parts.append(f"- {name} ({dtype}): {desc}")
            parts.append(f"**Result:** {result}")

    parts.extend([
        "",
        "## >>> CURRENT STEP (FOCUS HERE) <<<",
        "This is the current step you need to execute. Focus on completing THIS step below:",
        "",
        f"\n >>> {current_step.step_description} <<< \n",
        "",
    ])

    # Input variables
    input_vars = current_step.input_variables or []
    if input_vars:
        parts.append("### Input variables available")
        if isinstance(input_vars, dict):
            for name, dtype in input_vars.items():
                parts.append(f"- {name}: {dtype}")
        else:
            for var in input_vars:
                name = getattr(var, "variable_name", "")
                dtype = getattr(var, "variable_data_type", "")
                desc = getattr(var, "variable_description", "")
                parts.append(f"- {name} ({dtype}): {desc}")
        parts.append("")

    # Output variables
    output_vars = current_step.output_variables or []
    if output_vars:
        parts.append("### Output variables required")
        if isinstance(output_vars, dict):
            for name, dtype in output_vars.items():
                parts.append(f"- {name}: {dtype}")
        else:
            for var in output_vars:
                name = getattr(var, "variable_name", "")
                dtype = getattr(var, "variable_data_type", "")
                desc = getattr(var, "variable_description", "")
                parts.append(f"- {name} ({dtype}): {desc}")
        parts.append("")

    return "\n".join(parts)
