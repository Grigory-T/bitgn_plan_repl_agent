# PAC1 Architecture

This document describes the final architecture of `key_concept - plan_repl_agent` that was used in the BitGN PAC1 competition.

Run:
- `run-22HnfFFXgmjTw4nigcpQpLD88`

Result:
- `60.6 / 104`

Models:
- Planning: `openai/gpt-5.4`
- After-step decision: `openai/gpt-5.4`
- Final response compilation: `openai/gpt-5.4`
- Step execution: `z-ai/glm-5.1`

All main model calls were routed through OpenRouter.

## How it works

The architecture has four main layers.

1. Preflight check.
The agent first checks whether the task is clearly unsafe, conflicting, malicious, or impossible to execute reliably. If yes, it aborts early instead of entering the full execution loop.

2. Planning.
A strong structured-output model (`openai/gpt-5.4`) creates a linear sequence of plan steps. Each step includes a description plus exact expected output variables with names and Python dtypes.

3. Step execution.
Each step is solved in an isolated LLM context by a coding-oriented model (`z-ai/glm-5.1`). The model generates Python code inside explicit `<python> ... </python>` blocks. The code is executed, the result is appended back into the conversation, and the loop continues until the model finalizes the step. Python globals are shared across steps, so completed steps can pass variables directly to later ones.

4. After-step decision and final response.
After every completed step, `openai/gpt-5.4` decides whether to continue, abort, mark the task as completed, or replan the remaining steps. Final response compilation is also handled by `openai/gpt-5.4`, including PAC1-specific mapping to benchmark outcomes and grounding refs.

## Problems encountered

The main difficulty was that, in practice, I was mostly limited to prompt work, while the architecture itself was reused almost unchanged from the previous challenge. I still consider this architecture close to optimal, or at least a strong baseline. The problem was that prompt changes affected behavior in complex ways, and there were several prompts interacting at once. I tuned them manually and did not use any evolutionary or automated prompt-optimization approach. As a result, the prompts gradually grew large and harder to control. This was probably the main design problem.

## How they were solved

I would not say that I solved this problem in a fundamental way. The prompts still grew larger, and I mostly kept adjusting or rewriting particular formulations. That improved behavior in some places, but it did not fully resolve the underlying issue. In practice, the main compensation was using stronger models than in the previous iteration, even if they were not the strongest available.

## How this agent could be made even better

This remains an open question. It is not obvious to me in which direction the architecture itself should be changed. Most likely, improvement would require much deeper analysis of the practical tasks one by one: how the agent should have acted in each concrete situation, why it acted differently, and which part of the system influenced that behavior. Stronger models may help, but I still do not see an obvious architectural change that would clearly solve the problem.

## What I learned

The main lesson for me was that the architecture is reusable, but it still has serious weaknesses. A score around sixty points out of one hundred means that something is suboptimal, but it is not obvious exactly where. It is unclear whether the right direction is to change the architecture, change the models, or keep changing prompts. I still do not have a final answer to that question. More broadly, I learned that agent behavior is highly complex, and if the goal is to move from a medium result to something much stronger, such as eighty or ninety points, then deeper changes are needed, not only prompt edits. Compared with my previous version, most of my changes were in prompts, and this experience showed the limits of that approach.

## Related links

- Competition submission text:
  - `bitgn-architectures/2026-04-11-pac1/key_concept_architecture.md`
- Contest code branch:
  - `pac1`
- Later cleaned general-purpose branch:
  - `general_purpose`
