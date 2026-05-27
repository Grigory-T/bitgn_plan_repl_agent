# plan_repl_agent ECOM

BitGN ECOM agent based on the old `plan_repl_agent` staged-run interface.

## What This Repo Is

This repo is the editable ECOM competition agent. It is developed and executed
locally on this laptop in:

```bash
/home/linuxuser/bitgn-ecom
```

The implementation keeps the old plan/repl orchestration style:

- explicit `start-run`, `run-tasks`, `status`, `end-run` lifecycle
- durable run state in `runs/`
- per-batch and per-task logs in `logs/`
- selective task reruns before final submission
- no automatic submission from `run-tasks`
- legacy one-shot mode for quick local batches

## Prerequisites

- `.env` copied or adapted from `.env.sample`
- provider keys configured in `.env`
- `BITGN_API_KEY` configured in `.env` for staged run flow
- this repo's local `.venv` created with `./setup_venv.sh`

Environment loading notes:

- `run_bitgn_task.py` loads `.env` automatically via `python-dotenv`
- you do not need to prefix commands with env vars if `.env` already contains them
- you can still override a value inline for one command

Important env vars:

- `OPENROUTER_API_KEY`
- `CEREBRAS_API_KEY`
- `LLM_AGENT_PROVIDER`
- `BITGN_API_KEY`
- `BENCHMARK_ID` or `BENCH_ID`
- `BITGN_HOST` or `BENCHMARK_HOST`
- `BITGN_RUN_NAME`
- `BITGN_WORKERS`

Install dependencies:

```bash
./setup_venv.sh
```

This repo vendors generated BitGN protobuf/connect modules under `bitgn/`
because the public Buf wheels used by the sample ECOM agent were not fetchable
from this laptop.

## Local Sync

The old PAC1 repo had optional sync infrastructure for `/home/linuxuser/bitgn`.
There is no equivalent ECOM sync step here now. Normal execution is local from
`/home/linuxuser/bitgn-ecom`.

## Run On This Laptop

```bash
cd /home/linuxuser/bitgn-ecom
./setup_venv.sh
.venv/bin/python3 run_bitgn_task.py start-run --task-id t00-t47 --benchmark-id <published-ecom-benchmark-id>
```

Recommended staged flow:

```bash
cd /home/linuxuser/bitgn-ecom
.venv/bin/python3 run_bitgn_task.py start-run --task-id t00-t47 --benchmark-id <published-ecom-benchmark-id>
.venv/bin/python3 run_bitgn_task.py run-tasks --run-id latest --task-id t00-t09 --workers 4
.venv/bin/python3 run_bitgn_task.py run-tasks --run-id latest --task-id t10-t19 --workers 4
.venv/bin/python3 run_bitgn_task.py run-tasks --run-id latest --task-id t03,t07,t18 --workers 3
.venv/bin/python3 run_bitgn_task.py status --run-id latest
.venv/bin/python3 run_bitgn_task.py end-run --run-id latest
```

Notes:

- `start-run` requires `BITGN_API_KEY`
- for production, switch only `--benchmark-id` to the published ECOM benchmark id
- ECOM does not expose playground trials, so prepared run trials are required
- task ids are zero-based when the benchmark starts at `t00`, and three-digit ids such as `t100` are supported
- the runner tolerates missing score/details fields and waits for prepared trials before starting task workers
- `run-tasks` and `end-run` operate on durable local run state in `runs/`
- `run-tasks` can be repeated with any subset before final submission
- if `--task-id` is omitted on `run-tasks`, all locally unfinished tasks run
- `run-tasks` does not submit the run
- `status` is read-only
- `end-run` submits the run explicitly
- if `end-run` finds unfinished local tasks, it force-submits them with:
  - outcome: `OUTCOME_DENIED_SECURITY`
  - refs: empty
  - this is an intentional conservative fallback for any still-unanswered tasks
- all staged commands print a human-readable `STARTED_AT ...` line
- `start-run` prints `RUN_ID ...` and `RUN_STATE ...`

Current DEV smoke benchmark note:

```bash
.venv/bin/python3 run_bitgn_task.py start-run --task-id t01-t48 --benchmark-id bitgn/ecom1-dev
```

As of 2026-05-27, `bitgn/ecom1-dev` reports `t01-t48`. The competition
benchmark can start at `t00`; use the benchmark's actual task ids.

Debug mode:

```bash
.venv/bin/python3 run_bitgn_task.py run-tasks --run-id latest --task-id t07 --workers 1 -d
.venv/bin/python3 run_bitgn_task.py run-tasks --run-id latest --task-id t01-t03 --workers 3 -d
```

In `-d` mode:

- no LLM pipeline is used
- each worker starts its prepared trial and immediately submits a forced preflight denial
- this is intended only for log/debug inspection and parallel runner checks

Legacy one-shot mode still exists:

```bash
.venv/bin/python3 run_bitgn_task.py --task-id t08 --benchmark-id bitgn/ecom1-dev
.venv/bin/python3 run_bitgn_task.py --task-id t00,t03,t100 --benchmark-id <published-ecom-benchmark-id> --workers 4
.venv/bin/python3 run_bitgn_task.py --task-id t00-t05 --benchmark-id <published-ecom-benchmark-id> --workers 4
```

One-shot mode starts a BitGN run, executes the selected tasks, then submits that
run in the old style. Unlike old PAC1, ECOM does not expose playground trials,
so one-shot mode also requires `BITGN_API_KEY`. The staged lifecycle is
preferred for competition work.

## Logs And State

Run logs are written locally under:

```bash
/home/linuxuser/bitgn-ecom/logs/
```

Durable run orchestration state is stored separately under:

```bash
/home/linuxuser/bitgn-ecom/runs/
```

Important separation:

- `runs/` stores durable run metadata and `task_id -> trial_id` mapping
- `logs/` stores per-batch and per-task execution traces
- `logs/<batch_id>/batch_runner_state.txt` stores batch-level status and score/details summaries

Run identity and state:

```bash
runs/<run_id>/run_state.json
runs/latest_run.txt
```

Execution logs:

```bash
logs/<batch_id>/batch_runner_state.txt
logs/<batch_id>/<task_id>/
```

Important files inside each task log directory:

- `runner_state.txt`
- `task_result.txt`
- `bitgn_evaluation.txt`
- `final_response.txt`
- planner and step logs from `plan_agent/`

## Current Runtime Model

Control plane:

- leaderboard mode supports the old 3-stage lifecycle:
  - `start-run`
  - `run-tasks`
  - `end-run`
- `start-run` creates one BitGN run and stores local run state
- `run-tasks` attaches to an existing run and executes any selected subset of tasks
- `end-run` explicitly submits the run
- this keeps run lifetime visible and allows manual reruns before final submission

Per-task execution:

- start prepared trial via BitGN harness
- receive `trial_id`, `instruction`, `harness_url`
- run the planner/executor agent loop
- submit final `message + outcome + refs`
- end the trial and read evaluation

Runtime plane:

- ECOM runtime, not PAC1 PCM runtime
- wrapper exposed through `ecom_runtime.py`
- final submission uses the ECOM `answer` RPC

## Main Files

- `run_bitgn_task.py` - BitGN runner with staged lifecycle and legacy one-shot mode. Uses one separate worker process per task, bounded by `--workers`. No task retry is performed. Worker failures do not stop the batch.
- `ecom_runtime.py` - ECOM runtime adapter exposed to executed Python as `bitgn`
- `plan_repl_agent.py` - local single-task workspace runner
- `plan_agent/run_agent.py` - plan/step loop
- `plan_agent/run_step.py` - per-step Python REPL loop
- `plan_agent/prompt_agent.py` - ECOM tool/safety prompt
- `plan_agent/response.py` - final `message`, `outcome`, `refs` decision
- `bitgn/` - generated protobuf modules and small ConnectRPC clients

## Current Run Lifecycle

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

Important design rules:

- `start-run` writes state once and does not overwrite silently
- `run-tasks` must not auto-submit
- `end-run` must not execute tasks
- task logs include `task_id` and `trial_id`
- batch logs stay separate from durable run state
- local run-state files are the source of truth for manual operation

## Notes

- `.env` is ignored by Git
- `.venv/` is ignored by Git
- `logs/` is ignored by Git
- `runs/` is ignored by Git
- old PAC1 and sample-agent repos are reference sources, not the main place for ECOM edits
