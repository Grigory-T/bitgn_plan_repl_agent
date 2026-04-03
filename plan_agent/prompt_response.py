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
- refs: list of grounding refs inferred only from the step results (**directly or indirectly used**)

Rules:
- Final refs and any file-path answer must preserve the exact runtime path string required by the workspace rules, examples, and step results
- Do not add or remove a leading `/` unless the workspace evidence shows that exact form
- Use only the file paths already mentioned in the step results
- The step results are the only allowed source of refs

# Response/answer formulation
- you need to carefully consider how to formulate response/anser
- look for any rules/recommendations in instructions on how to formulate response/anser
- follow these rules/recommendations strictly (verbatim literal exection)

"""
