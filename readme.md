# plan_repl_agent

Planning agent with a local work loop and a separate final response phase.

## Current Picture

This project no longer uses:
- Docker
- HTTP server
- git or GitHub metadata inside the workspace

The working model is now:
1. local laptop files are the source of truth
2. `bitgn` is the execution machine
3. edit locally
4. sync to `bitgn`
5. run on `bitgn`

So this repository is now a plain file tree, not a git checkout.

## Main Workflow

### 1. Edit Locally

Work in:

```bash
/home/linuxuser/bitgn/plan_repl_agent
```

This laptop copy is the main version you edit.

### 2. Sync To BitGN

Push local changes to the execution machine:

```bash
rsync -az --delete /home/linuxuser/bitgn/plan_repl_agent/ bitgn:~/bitgn/plan_repl_agent/
```

Use this after local edits and before running on `bitgn`.

For frequent use, prefer the helper scripts in `/home/linuxuser/bitgn`:

```bash
/home/linuxuser/bitgn/sync-bitgn.sh
```

What it does:
- clears local runtime artifacts for `plan_repl_agent`
- clears remote runtime artifacts on `bitgn`
- syncs `plan_repl_agent` including `.env`
- syncs `sample-agents`
- syncs `erc3-prod-key-concept-score-67`

For a quick code-only validation after sync:

```bash
/home/linuxuser/bitgn/sync-plan-agent.sh
```

This runs the sync and then checks remote `plan_repl_agent` syntax.
It also makes sure the remote `.venv` exists before the check.

### 3. Run On BitGN

This repo is focused on the BitGN contest workflow.

Normal entrypoint on `bitgn`:

```bash
./setup_venv.sh
.venv/bin/python -B run_bitgn_task.py --task-id t04
```

That script:
1. starts the BitGN trial
2. gets the real task instruction and harness URL
3. runs a separate preflight check
4. runs the planning agent
5. calls `EndTrial`
6. writes BitGN evaluation into the same log directory

## Execution Architecture

The flow is:
1. `run_bitgn_task.py` starts one BitGN trial
2. `plan_agent/preflight.py` performs a fast separate preflight check
3. `plan_agent/run_agent.py` creates a plan
4. `plan_agent/run_step.py` executes plan steps with an LLM loop
5. each step uses Python and bash snippets
6. after the work phase ends, `plan_agent/response.py` creates the final response
7. the launcher submits through `bitgn.answer(...)`

Important separation:
- work phase: gather facts, inspect files, compute, edit, prepare result
- response phase: convert raw work result into the final answer
- BitGN submission: only in the response phase

## Main Files

- `run_bitgn_task.py`: BitGN contest entrypoint
- `setup_venv.sh`: creates or refreshes the shared `.venv`
- `plan_agent/preflight.py`: separate preflight check before planning
- `plan_agent/prompt_preflight.py`: preflight rules
- `plan_agent/run_agent.py`: top-level planning and step execution loop
- `plan_agent/run_step.py`: LLM loop for one step
- `plan_agent/plan.py`: plan, decision, replan structures
- `plan_agent/executor.py`: Python/bash execution with persistent Python globals
- `plan_agent/response.py`: separate post-work final response phase
- `plan_agent/prompt_agent.py`: work-phase rules for the LLM
- `plan_agent/prompt_plan.py`: planning rules
- `plan_agent/prompt_response.py`: final response rules
- `bitgn_runtime.py`: typed BitGN runtime helper module
- `bitgn_sdk/`: vendored BitGN mini-runtime client code

## BitGN Mode

`run_bitgn_task.py` is the intended BitGN contest launcher.

During the work phase, Python snippets can use:
- `bitgn.outline(...)`
- `bitgn.search(...)`
- `bitgn.list(...)`
- `bitgn.read(...)`
- `bitgn.write(...)`
- `bitgn.delete(...)`

Rules:
- work phase may inspect and modify the BitGN runtime workspace
- work phase must not call `bitgn.answer(...)`
- only the separate response phase submits the final BitGN answer

## Logs And Work Directories

- `logs/<timestamp>/plan.txt`: initial plan and replans
- `logs/<timestamp>/preflight.txt`: preflight decision
- `logs/<timestamp>/decisions.txt`: after-step decisions
- `logs/<timestamp>/step_N/messages.txt`: prompts, code, and execution results
- `logs/<timestamp>/step_N/reasoning.txt`: captured reasoning text when available
- `work/<run_id>/`: per-run local working directory

## Environment

Minimal `.env`:

```env
OPENROUTER_API_KEY=...
```

Model defaults are set in `plan_agent/utils.py`.

`.env` is included in the normal sync now.
One sync command mirrors code and environment files together.

## Virtual Environment

The project uses one shared `.venv` only on `bitgn`:
- remote: `~/bitgn/plan_repl_agent/.venv`

Rules:
- do not keep a project `.venv` on the laptop
- do not recreate the remote environment for each run
- do not sync `.venv` between machines
- refresh the remote environment with `./setup_venv.sh` when dependencies change
- run the agent on `bitgn` with `.venv/bin/python -B`

## Related Directories

In `/home/linuxuser/bitgn` there are currently three related plain-file directories:

- `plan_repl_agent`: the project you edit and run
- `sample-agents`: BitGN reference samples and proto-generated clients
- `erc3-prod-key-concept-score-67`: reference project used to copy the separate response-stage pattern

How to treat them:
- edit `plan_repl_agent` as the main project
- use `sample-agents` only as reference/examples for BitGN runtime behavior
- use `erc3-prod-key-concept-score-67` only as reference/examples for architecture ideas

## Important Constraints

- no `.git` folders remain locally or on `bitgn`
- do not treat this directory as a git repository
- local laptop files are the editable master copy
- `bitgn` is the execution engine
- after local edits, sync before any real remote run
- use `/home/linuxuser/bitgn/sync-bitgn.sh` as the default frequent sync path

## Current Limitations

- BitGN `t01` is still unstable
- internet search in the work phase needs stronger fallback behavior
- some live runs can loop when external sources are weak, blocked, or inconsistent
- the separate response phase is already in place, but BitGN benchmark behavior still needs tuning
