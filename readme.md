# plan_repl_agent

General-purpose planning and execution agent for local file workspaces.

## What This Branch Is

This branch keeps only the reusable local agent core:

- planning
- per-step execution
- Python-only code execution
- structured step completion
- isolated logs
- isolated per-run workspace

## Quick Start

From the repo root:

```bash
./setup_venv.sh
.venv/bin/python3 plan_repl_agent.py "create .txt file with ten words"
```

The command creates a fresh run under:

```bash
runs/<run_id>/
```

Each run contains:

- `workspace/`
  - the isolated workspace the agent can read and modify
- `step_logs/`
  - execution logs for the run
- `task.txt`
  - the original task text
- `result.json`
  - final structured result
- `final_answer.txt`
  - final user-facing answer

## Runtime Model

The executor is Python-only. There is no shell tool in the agent loop.
Each step runs plain Python code with:

- `WORKSPACE_ROOT`
  - absolute path to the writable workspace directory for the current run

The Python execution environment uses `WORKSPACE_ROOT` as its working directory.

## Main Files

- `plan_repl_agent.py`
  - single-run entrypoint
- `plan_agent/run_agent.py`
  - main plan/step loop
- `plan_agent/run_step.py`
  - per-step LLM loop
- `plan_agent/executor.py`
  - Python execution environment

## Environment

Create `.env` from `.env.sample`.

Required keys depend on provider choice:

- `OPENROUTER_API_KEY`
- `CEREBRAS_API_KEY`
- `LLM_AGENT_PROVIDER`

Current defaults are defined in `plan_agent/utils.py`.

## Notes

- `runs/` is ignored by Git.
