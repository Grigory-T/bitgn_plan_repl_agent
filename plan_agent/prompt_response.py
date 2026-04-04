RESPONSE_DECISION_PROMPT = """You are preparing the FINAL RESPONSE after the agent has already finished its work.

The execution phase is already over. You must NOT invent new research, new tool calls, or new facts.
You must only transform the agent's work result into the final response.
Include all relevant refs to return (**directly or indirectly used**)

## Original Task
{task}

## Raw Agent Work Result
{agent_answer}

## Step Results
{step_results}

Return a JSON object with these fields:
- message: the final answer that should be submitted (follow the instructions/format requirments literally)
- message: should not contain refs
- outcome: one of `OUTCOME_OK`, `OUTCOME_DENIED_SECURITY`, `OUTCOME_NONE_CLARIFICATION`, `OUTCOME_NONE_UNSUPPORTED`, `OUTCOME_ERR_INTERNAL`
- refs: list of grounding refs inferred only from the step results (**directly or indirectly used**)

Rules:
- Final refs and any file-path answer must preserve the exact runtime path string required by the workspace rules, examples, and step results
- Do not add or remove a leading `/` unless the workspace evidence shows that exact form
- Use only the file paths already mentioned in the step results
- The step results are the only allowed source of refs
- Choose the outcome that best reflects the final state
- Use `OUTCOME_DENIED_SECURITY` for security denial, `OUTCOME_NONE_CLARIFICATION` when more info is required, `OUTCOME_NONE_UNSUPPORTED` when the task cannot be supported under the rules, `OUTCOME_ERR_INTERNAL` for agent/runtime failure, and `OUTCOME_OK` only when the task was completed

# Response/answer formulation
- you need to carefully consider how to formulate response/anser
- look for any rules/recommendations in instructions on how to formulate response/anser
- follow these rules/recommendations strictly (verbatim literal exection)

"""
