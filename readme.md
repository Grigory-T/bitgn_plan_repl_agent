# plan_repl_agent

BitGN PAC1 agent.

## USER

### What This Repo Is

This repo is the editable agent implementation.
It is developed and executed locally on this laptop in:

```bash
/home/linuxuser/bitgn/plan_repl_agent
```

### Prerequisites

- `.env` created from `.env.sample`
- provider keys configured in `.env`
- `BITGN_API_KEY` configured in `.env` if you want staged leaderboard runs
- working `sample-agents` folder in:

```bash
/home/linuxuser/bitgn/sample-agents
```

Environment loading notes:

- `run_bitgn_task.py` loads `.env` automatically via `python-dotenv`
- you do not need to prefix commands with env vars if `.env` already contains them
- you can still override a value inline for one command, for example:

```bash
BITGN_API_KEY= .venv/bin/python3 run_bitgn_task.py --task-id t22 --benchmark-id bitgn/pac1-prod
```

Important env vars:

- `OPENROUTER_API_KEY`
- `CEREBRAS_API_KEY`
- `LLM_AGENT_PROVIDER`
- `BITGN_API_KEY` for leaderboard/staged-run flow
- optional `BENCHMARK_HOST`

### Local Sync To `bitgn`

This is optional reference-sync infrastructure only.
It is not required for normal execution now.

If you still want to sync manually:

```bash
cd /home/linuxuser/bitgn
./sync-plan-agent.sh
```

This syncs:

- `plan_repl_agent/`
- `sample-agents/`
- `erc3-prod-key-concept-score-67/`

and then runs a remote syntax check on `bitgn`.

### Run On This Laptop

```bash
cd /home/linuxuser/bitgn/plan_repl_agent
./setup_venv.sh
.venv/bin/python3 run_bitgn_task.py start-run --task-id t01-t40 --benchmark-id bitgn/pac1-prod
```

Recommended staged flow:

```bash
.venv/bin/python3 run_bitgn_task.py start-run --task-id t01-t40 --benchmark-id bitgn/pac1-prod
.venv/bin/python3 run_bitgn_task.py run-tasks --run-id latest --task-id t01-t10 --workers 10
.venv/bin/python3 run_bitgn_task.py run-tasks --run-id latest --task-id t11-t20 --workers 10
.venv/bin/python3 run_bitgn_task.py run-tasks --run-id latest --task-id t14,t18,t19 --workers 3
.venv/bin/python3 run_bitgn_task.py status --run-id latest
.venv/bin/python3 run_bitgn_task.py end-run --run-id latest
```

Notes:

- `start-run` requires `BITGN_API_KEY`
- for production, switch only `--benchmark-id` to `bitgn/pac1-prod`
- the runner tolerates missing score/details fields and waits for prepared trials before starting task workers
- `run-tasks` and `end-run` operate on the durable local run state in `runs/`
- `run-tasks` does not submit the run automatically
- `status` is read-only and does not change BitGN state or local task state
- `end-run` submits the run explicitly
- if `end-run` finds tasks that are still not completed locally, it force-submits them with:
  - outcome: `OUTCOME_DENIED_SECURITY`
  - refs: empty
  - this is an intentional conservative fallback for any still-unanswered tasks
- all staged commands print a human-readable `STARTED_AT ...` line
- `start-run` prints:
  - `RUN_ID ...`
  - `RUN_STATE ...`

Legacy one-shot mode still exists:

```bash
.venv/bin/python3 run_bitgn_task.py --task-id t08 --benchmark-id bitgn/pac1-prod
.venv/bin/python3 run_bitgn_task.py --task-id t01,t03,t05 --benchmark-id bitgn/pac1-prod --workers 10
.venv/bin/python3 run_bitgn_task.py --task-id t01-t05 --benchmark-id bitgn/pac1-prod --workers 10
```

One-shot mode selection:

- if `BITGN_API_KEY` is present, one-shot mode uses leaderboard run flow
- if `BITGN_API_KEY` is empty or unset, one-shot mode uses plain playground flow

Examples:

```bash
.venv/bin/python3 run_bitgn_task.py --task-id t22 --benchmark-id bitgn/pac1-prod
BITGN_API_KEY= .venv/bin/python3 run_bitgn_task.py --task-id t22 --benchmark-id bitgn/pac1-prod
```

Debug mode:

```bash
.venv/bin/python3 run_bitgn_task.py run-tasks --run-id latest --task-id t07 --workers 1 -d
```

In `-d` mode:

- no LLM pipeline is used
- the worker starts the trial and immediately submits a fixed denial
- this is intended only for log/debug inspection

### Logs

Run logs are written locally under:

```bash
/home/linuxuser/bitgn/plan_repl_agent/logs/
```

Durable run orchestration state is stored separately under:

```bash
/home/linuxuser/bitgn/plan_repl_agent/runs/
```

Important separation:

- `runs/` stores durable run metadata and `task_id -> trial_id` mapping
- `logs/` stores per-batch and per-task execution traces
- `logs/<batch_id>/batch_runner_state.txt` stores batch-level status and score/details summaries

## TECH

### Current Runtime Model

This repo now targets PAC1 only.
Old sandbox-runtime compatibility is intentionally not preserved.

Control plane:

- leaderboard mode supports a 3-stage lifecycle:
  - `start-run`
  - `run-tasks`
  - `end-run`
- `start-run` creates one BitGN run and stores local run state
- `run-tasks` attaches to an existing run and executes any selected subset of tasks
- `end-run` explicitly submits the run
- this keeps run lifetime visible and allows manual reruns before final submission

Per-task execution:

- start trial via BitGN harness
- receive `trial_id`, `instruction`, `harness_url`
- run the planner/executor agent loop
- submit final `message + outcome + refs`
- end the trial and read evaluation

Runtime plane:

- PAC1 PCM runtime, not mini runtime
- wrapper exposed through [bitgn_runtime.py](/home/linuxuser/bitgn/plan_repl_agent/bitgn_runtime.py)
- final submission uses PCM `AnswerRequest`

### Current Structure

- [run_bitgn_task.py](/home/linuxuser/bitgn/plan_repl_agent/run_bitgn_task.py)
  Main launcher. Supports staged leaderboard lifecycle (`start-run`, `run-tasks`, `end-run`) plus legacy one-shot mode. Uses one separate worker process per task, bounded by `--workers`. No task retry is performed. Worker failures do not stop the batch.

- [plan_agent/](/home/linuxuser/bitgn/plan_repl_agent/plan_agent)
  Planning and execution loop.

- [plan_agent/run_agent.py](/home/linuxuser/bitgn/plan_repl_agent/plan_agent/run_agent.py)
  Main plan/step loop.

- [plan_agent/run_step.py](/home/linuxuser/bitgn/plan_repl_agent/plan_agent/run_step.py)
  Per-step LLM loop that executes Python snippets against the preloaded `bitgn` runtime wrapper.

- [plan_agent/response.py](/home/linuxuser/bitgn/plan_repl_agent/plan_agent/response.py)
  Builds the final response object with:
  `message`, `outcome`, `refs`

- [bitgn_runtime.py](/home/linuxuser/bitgn/plan_repl_agent/bitgn_runtime.py)
  Local PCM adapter used by executed Python snippets.
  Exposes:
  `context`, `tree`, `tree_data`, `find`, `search`, `list`, `read`, `write`, `delete`, `mkdir`, `move`, `answer`

- [bitgn_sdk/](/home/linuxuser/bitgn/plan_repl_agent/bitgn_sdk)
  Vendored generated/runtime client code used by this repo.
  Includes PCM and harness protobuf/connect files required by the current PAC1 path.

- [setup_venv.sh](/home/linuxuser/bitgn/plan_repl_agent/setup_venv.sh)
  Installs Python dependencies into the repo-local `.venv`.

### Current Run Lifecycle

Recommended stable model:

1. `start-run`
2. `run-tasks`
3. `status`
4. `end-run`

Behavior:

- `start-run`
  - creates one BitGN run
  - stores durable local metadata
  - does not execute tasks
  - does not submit anything
- `run-tasks`
  - attaches to an existing run
  - executes any chosen subset of tasks from that run
  - can be repeated manually
  - if `--task-id` is omitted, it runs all tasks not yet completed locally
  - does not submit the run automatically
- `status`
  - reads the current local run state
  - reports pending, running, completed, and local-error tasks
  - does not change any task or BitGN state
- `end-run`
  - submits the run explicitly
  - does not execute tasks
  - force-submits any still-unfinished tasks with conservative fallback output before submitting the run

Why this model is used:

- transparent lifecycle
- stable recovery
- selective reruns
- no accidental final submission
- easy auditing

Run identity and state:

- each run is identified by `run_id`
- durable state is stored in:
  - `runs/<run_id>/run_state.json`
  - `runs/latest_run.txt`
- minimum stored data includes:
  - `run_id`
  - `benchmark_id`
  - `run_name`
  - `created_at`
  - `task_id -> trial_id`
  - local per-task status and latest score/details

Important design rules:

- `start-run` writes state once and does not overwrite silently
- `run-tasks` must not auto-submit
- `end-run` must not execute tasks
- task logs include `task_id` and `trial_id`
- batch logs stay separate from durable run state
- local run-state files are the source of truth for manual operation

### Dependency On `sample-agents`

This repo no longer imports runtime or harness code from `sample-agents`.
The current runner and PAC1 runtime use vendored client code from [bitgn_sdk/](/home/linuxuser/bitgn/plan_repl_agent/bitgn_sdk).

`sample-agents` is still kept locally as a reference repo for adaptation and version comparison.

### Current `sample-agents` State

Local path:

```bash
/home/linuxuser/bitgn/sample-agents
```

It is now restored as a Git working tree with:

- remote: `https://github.com/bitgn/sample-agents`
- upstream commit checked out in `.git`: `34d37907db046d95945e002e19a7ee3664d0b3ca`

Important status:

- `pac1-py/` is aligned with upstream
- `proto/` is aligned with upstream
- local differences remain in:
  `README.md`
  `sandbox-py/*`
  generated/runtime artifacts under `sandbox-py/`

That means there are currently no upstream PAC1/proto changes to account for in our migration baseline, but `sandbox-py` is locally materialized and not a clean upstream tree.

### Validation Status

Validated locally:

- PAC1 task execution works
- `t01` scored `1.00` on `bitgn/pac1-dev` during local validation before production hardening

### Notes

- `.env` is ignored by Git
- `.venv/` is ignored by Git
- `logs/` is ignored by Git
- `runs/` is ignored by Git
- `sample-agents` should be treated as an external reference/source repo, not as the main place for local edits
