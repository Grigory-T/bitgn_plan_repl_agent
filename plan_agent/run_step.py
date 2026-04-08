import ast
from typing import Any, get_args, get_origin
from pathlib import Path
from typeguard import check_type

from .utils import llm, LLM_MODEL_AGENT, check_assigned_variables, format_step_variables
from .prompt_agent import STEP_SYSTEM_PROMPT, build_step_user_first_msg_prompt
from .executor import execute_python, execute_bash, PERSISTENT_GLOBALS
from .log import _append_step_log, _append_reasoning, _write_log

MAX_ITERATIONS_PER_STEP = 30
INITIAL_TREE_MAX_CHARS = 6000
MAX_EMPTY_LLM_REPLIES_PER_STEP = 25
MAX_TOTAL_EMPTY_LLM_REPLIES_PER_STEP = 60


def _truncate_for_prompt(text: str, limit: int = INITIAL_TREE_MAX_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n... [truncated]"


def _build_input_variables_code(current_step) -> str | None:
    input_vars = current_step.input_variables or []
    names: list[str] = []

    if isinstance(input_vars, dict):
        names = [name for name in input_vars.keys() if name]
    else:
        for var in input_vars:
            name = getattr(var, "variable_name", "")
            if name:
                names.append(name)

    if not names:
        return None

    quoted_names = ", ".join(repr(name) for name in names)
    return f"""variable_names = [{quoted_names}]
print("INPUT VARIABLES SNAPSHOT")
for variable_name in variable_names:
    print("=" * 80)
    print(f"NAME: {{variable_name}}")
    print(f"TYPE: {{type(globals().get(variable_name)).__name__}}")
    print("VALUE:")
    print(globals().get(variable_name))
print("=" * 80)"""


def _matches_literal_dtype(value: Any, dtype: Any) -> bool:
    origin = get_origin(dtype)
    if origin is None:
        return isinstance(value, dtype)

    if origin is list:
        if not isinstance(value, list):
            return False
        args = get_args(dtype)
        if not args:
            return True
        return all(_matches_literal_dtype(item, args[0]) for item in value)

    if origin is tuple:
        if not isinstance(value, tuple):
            return False
        args = get_args(dtype)
        if not args:
            return True
        if len(args) == 2 and args[1] is Ellipsis:
            return all(_matches_literal_dtype(item, args[0]) for item in value)
        if len(value) != len(args):
            return False
        return all(_matches_literal_dtype(item, arg) for item, arg in zip(value, args))

    if origin is dict:
        if not isinstance(value, dict):
            return False
        key_type, value_type = get_args(dtype)
        return all(
            _matches_literal_dtype(key, key_type) and _matches_literal_dtype(item, value_type)
            for key, item in value.items()
        )

    if origin is set:
        if not isinstance(value, set):
            return False
        args = get_args(dtype)
        if not args:
            return True
        return all(_matches_literal_dtype(item, args[0]) for item in value)

    if str(origin) == "typing.Union":
        return any(_matches_literal_dtype(value, arg) for arg in get_args(dtype))

    return isinstance(value, origin)


def _validate_output_value(value: Any, dtype: Any) -> None:
    try:
        check_type(value, dtype)
        return
    except Exception:
        pass

    if _matches_literal_dtype(value, dtype):
        return

    raise TypeError(f"value does not match {dtype}")

def run_step(task, current_step, completed_steps, log_dir=None, step_index=0) -> str:
    step_folder = Path(log_dir) / f"step_{step_index}" if log_dir else None
    messages_log = step_folder / "messages.txt" if step_folder else None
    reasoning_log = step_folder / "reasoning.txt" if step_folder else None

    system_prompt = STEP_SYSTEM_PROMPT
    user_prompt = build_step_user_first_msg_prompt(
        task=task,
        current_step=current_step,
        completed_steps=completed_steps,
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    _append_step_log(messages_log, "system", system_prompt)
    _append_step_log(messages_log, "user", user_prompt)

    initial_tree_code = "print(bitgn.tree_with_line_counts('/'))"
    initial_assistant_msg = f"<python>\n{initial_tree_code}\n</python>"
    messages.append({"role": "assistant", "content": initial_assistant_msg})
    _append_step_log(messages_log, "assistant 0", initial_assistant_msg)

    initial_tree_response = execute_python(initial_tree_code)
    initial_result_parts = []
    if initial_tree_response.stdout:
        initial_result_parts.append(f"\n**STDOUT:**\n{_truncate_for_prompt(initial_tree_response.stdout)}")
    if initial_tree_response.stderr:
        initial_result_parts.append(f"**STDERR:**\n{_truncate_for_prompt(initial_tree_response.stderr)}")
    initial_block_result = (
        "Code execution result:\n" + "\n\n".join(initial_result_parts)
        if initial_result_parts
        else "Code execution result: (no output)"
    )
    messages.append({"role": "user", "content": initial_block_result})
    _append_step_log(messages_log, "user 0", initial_block_result)

    input_variables_code = _build_input_variables_code(current_step)
    if input_variables_code:
        initial_input_msg = f"<python>\n{input_variables_code}\n</python>"
        messages.append({"role": "assistant", "content": initial_input_msg})
        _append_step_log(messages_log, "assistant input", initial_input_msg)

        input_variables_response = execute_python(input_variables_code)
        input_result_parts = []
        if input_variables_response.stdout:
            input_result_parts.append(f"\n**STDOUT:**\n{input_variables_response.stdout}")
        if input_variables_response.stderr:
            input_result_parts.append(f"**STDERR:**\n{input_variables_response.stderr}")
        input_block_result = (
            "Code execution result:\n" + "\n\n".join(input_result_parts)
            if input_result_parts
            else "Code execution result: (no output)"
        )
        messages.append({"role": "user", "content": input_block_result})
        _append_step_log(messages_log, "user input", input_block_result)

    completed_turns = 0
    empty_replies = 0
    total_empty_replies = 0

    while completed_turns < MAX_ITERATIONS_PER_STEP:
        llm_response, llm_response_blocks, reasoning = llm(messages, model=LLM_MODEL_AGENT)
        _append_reasoning(reasoning_log, reasoning)

        if not llm_response and not llm_response_blocks:
            empty_replies += 1
            total_empty_replies += 1
            if total_empty_replies >= MAX_TOTAL_EMPTY_LLM_REPLIES_PER_STEP:
                failure_msg = (
                    "Step failed because the model returned too many empty replies in a row "
                    "and did not make progress."
                )
                if step_folder:
                    _write_log(step_folder / "step_result.txt", failure_msg)
                return failure_msg
            if empty_replies >= MAX_EMPTY_LLM_REPLIES_PER_STEP:
                user_msg = (
                    "The model returned too many empty replies in a row. "
                    "Continue with a concrete <python>...</python> block, or finish the step."
                )
                messages.append({"role": "user", "content": user_msg})
                _append_step_log(messages_log, "user", user_msg)
                empty_replies = 0
            continue

        empty_replies = 0
        completed_turns += 1

        if not llm_response_blocks:
            messages.append({"role": "assistant", "content": llm_response})
            _append_step_log(messages_log, "assistant", llm_response)
            continue

        if all(block.block_type == "text" for block in llm_response_blocks):
            messages.append({"role": "assistant", "content": llm_response})
            _append_step_log(messages_log, "assistant", llm_response)
            user_msg = ("No valid code to execute. Use \n<python>\n...\n</python>\ntags to write code.\n"
                        "If step is completed you should set python variables `step_status: str` - 'completed' or 'failed' and `final_answer: str` - description of results.\n"
                        )
            messages.append({"role": "user", "content": user_msg})
            _append_step_log(messages_log, "user", user_msg)
            continue

        pending_text = []
        python_blocks = []
        pair_idx = 0  # numbering for code/result pairs in logs

        for block in llm_response_blocks:
            if block.block_type == "text":
                pending_text.append(block.block_text)
                continue

            if block.block_type not in ("python", "bash"):
                continue

            code_type = block.block_type
            code = block.block_text

            assistant_msg = "".join(pending_text) + f"<python>\n{code}\n</python>"
            pending_text = []
            messages.append({"role": "assistant", "content": assistant_msg})
            _append_step_log(messages_log, f"assistant {pair_idx}", assistant_msg)

            if code_type == "python":
                code_response = execute_python(code)
                python_blocks.append(code)
            else:
                user_msg = f"Unknown code type: {code_type}"
                messages.append({"role": "user", "content": user_msg})
                _append_step_log(messages_log, "user", user_msg)
                continue

            result_parts = []
            if code_response.stdout:
                result_parts.append(f"\n**STDOUT:**\n{code_response.stdout}")
            if code_response.stderr:
                result_parts.append(f"**STDERR:**\n{code_response.stderr}")
            block_result = "Code execution result:\n" + "\n\n".join(result_parts) if result_parts else "Code execution result: (no output)"

            messages.append({"role": "user", "content": block_result})
            _append_step_log(messages_log, f"user {pair_idx}", block_result)
            pair_idx += 1

        # If only text blocks existed, surface them once
        if pending_text and not python_blocks and not any(b.block_type == "bash" for b in llm_response_blocks):
            text_msg = "".join(pending_text)
            messages.append({"role": "assistant", "content": text_msg})
            _append_step_log(messages_log, "assistant", text_msg)

        # Was final_answer or step_status assigned in any python block?
        vars_assigned = any(check_assigned_variables(b) for b in python_blocks)
        final_answer = PERSISTENT_GLOBALS.get('final_answer', '')
        step_status = PERSISTENT_GLOBALS.get('step_status', '')

        # True only if exactly one python block exists AND it assigns both step_status and final_answer (order doesn't matter)
        twoline_oneblock_code = False
        if len(llm_response_blocks) == 1 and llm_response_blocks[0].block_type == "python":
            try:
                tree = ast.parse(llm_response_blocks[0].block_text)
                if len(tree.body) != 2:
                    raise ValueError("not a two-line python finalize block")
                targets = set()
                for node in tree.body:
                    if isinstance(node, ast.Assign):
                        for t in node.targets:
                            if isinstance(t, ast.Name):
                                targets.add(t.id)
                            elif isinstance(t, (ast.Tuple, ast.List)):
                                for elt in t.elts:
                                    if isinstance(elt, ast.Name):
                                        targets.add(elt.id)
                if "final_answer" in targets and "step_status" in targets:
                    twoline_oneblock_code = True
            except Exception:
                pass

        if vars_assigned and final_answer and step_status and not twoline_oneblock_code:
            are_you_sure_msg = (
                'Make sure that the step is completed correctly and you understand the result.\n'
                'Analyze all the information above, facts and code execution results. You should base you descision on the information above.\n'
                f'The current step target was: >>>{current_step.step_description}<<<\n'
                f'The current step output variables (should be set if task is `completed`, `None` or empty containers ([], {{}} etc.) **is not allowed**):{format_step_variables(current_step.output_variables)}\n\n'
                'Report the exact runtime file paths that materially influenced this step.\n'
                'These may be direct files you acted on or indirect governing files that shaped what was correct.\n'
                'Copy path strings verbatim from tool output or file content. Do not add or remove a leading slash yourself.\n'
                'Inside `final_answer`, end with one exact line in this format:\n'
                '`Relevant files: path1, path2`\n'
                'or `Relevant files: none`\n\n'

                'If you are sure you want to finilize step: use **exactly** two lines of code\n'
                "\n<python>\nstep_status = 'completed' OR 'failed'\nfinal_answer = ...result description...\n</python>\n"

                'Do not include other code tags. Only one <python> block with two assignments.'
                'All other **Output variables required** - should be set in separate python block.'
                'So firstly set all required variables in separate step. Then in **separate** step assign final two variables: `step_status` and `final_answer`'
            )
            messages.append({"role": "user", "content": are_you_sure_msg})
            _append_step_log(messages_log, "user", are_you_sure_msg)
            continue

        if vars_assigned and final_answer and step_status and twoline_oneblock_code:
            if step_status == 'failed':
                if step_folder:
                    _write_log(step_folder / "step_result.txt", final_answer)
                return final_answer

            error_msg = ""
            for var in current_step.output_variables:
                name = var.variable_name
                dtype_str = var.variable_data_type
                value = PERSISTENT_GLOBALS.get(name, None)
                if value is None:
                    error_msg += f'Missing variable: {name}\n'
                else:
                    if dtype_str == 'object':
                        continue
                    try:
                        glbs = dict(PERSISTENT_GLOBALS)
                        if 'pd' in glbs and 'pandas' not in glbs:
                            glbs['pandas'] = glbs['pd']
                        if 'np' in glbs and 'numpy' not in glbs:
                            glbs['numpy'] = glbs['np']
                        
                        dtype = eval(dtype_str, glbs)
                        _validate_output_value(value, dtype)
                    except Exception as e:
                        error_msg += (f'Error: {name} is {type(value).__name__} but expected literal python type: {dtype_str}\n'
                                        f'make sure that the variable {dtype_str} class exists verbatim in current python environment.\n'
                                        f'name of the class should be verbatim {dtype_str}, so re-import it if needed\n'
                                        f'examples of different imports: import pandas as pd VS import pandas; import numpy as np VS import numpy; etc\n'
                                        )
            if not error_msg:
                if step_folder:
                    _write_log(step_folder / "step_result.txt", final_answer)
                return final_answer
            
            messages.append({"role": "user", "content": error_msg})
            _append_step_log(messages_log, "user", error_msg)

    fallback = "Max iterations reached without a final answer."
    if step_folder:
        _write_log(step_folder / "step_result.txt", fallback)
    return fallback
