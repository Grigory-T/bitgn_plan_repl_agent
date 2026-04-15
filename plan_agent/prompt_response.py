from .json_schemas import RESPONSE_DECISION_SCHEMA_JSON


def build_response_decision_prompt(task: str, agent_answer: str, step_results: str) -> str:
    return f"""You are preparing the final response after the agent has already finished its work.

## Original Task
{task}

## Raw Agent Work Result
{agent_answer}

## Step Results
{step_results}

Return a JSON object with exactly these fields:
- message: a useful final summary of the work done and the main conclusions for the user
- reasoning: a short internal explanation of why this summary is correct

JSON field rules:
- `message` should describe what was completed, the key result, and any important limitation or conclusion
- if the task required a strict output format, `message` must follow that format literally instead of adding summary prose
- `reasoning` must be concise and must not introduce new facts
- do not add any extra JSON fields

Use only the raw agent result and step results. Do not add research, new file paths, or extra commentary.

Return only JSON matching this schema:
{RESPONSE_DECISION_SCHEMA_JSON}
""".strip()
