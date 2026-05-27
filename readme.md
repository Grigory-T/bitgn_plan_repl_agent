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

## Setup

`.env` is loaded automatically by `run_bitgn_task.py`.

Required:

```bash
OPENROUTER_API_KEY=...
BITGN_API_KEY=...
```

Optional:

```bash
BENCHMARK_ID=bitgn/ecom1-dev
BITGN_HOST=https://api.bitgn.com
BITGN_RUN_NAME="plan_repl_agent ecom"
BITGN_WORKERS=4
```

Install dependencies:

```bash
./setup_venv.sh
```

This repo vendors generated BitGN protobuf/connect modules under `bitgn/`
because the public Buf wheels used by the sample agent were not fetchable from
this laptop.

## Run On This Laptop

Recommended staged flow:

```bash
cd /home/linuxuser/bitgn-ecom
.venv/bin/python3 run_bitgn_task.py start-run --task-id t00-t47 --benchmark-id <published-ecom-benchmark-id>
.venv/bin/python3 run_bitgn_task.py run-tasks --run-id latest --task-id t00-t09 --workers 4
.venv/bin/python3 run_bitgn_task.py run-tasks --run-id latest --task-id t10-t19 --workers 4
.venv/bin/python3 run_bitgn_task.py status --run-id latest
.venv/bin/python3 run_bitgn_task.py end-run --run-id latest
```

Notes:

- `start-run` requires `BITGN_API_KEY`
- for production, switch only `--benchmark-id` to the published ECOM benchmark id
- ECOM does not expose playground trials, so prepared run trials are required
- task ids are zero-based when the benchmark starts at `t00`, and three-digit ids such as `t100` are supported
- `run-tasks` can be repeated with any subset before final submission
- if `--task-id` is omitted on `run-tasks`, all locally unfinished tasks run
- `run-tasks` does not submit the run
- `status` is read-only
- `end-run` submits the run explicitly
- if `end-run` finds unfinished local tasks, it force-submits conservative denials before submitting the run
- all staged commands print a human-readable `STARTED_AT ...` line
- `start-run` prints `RUN_ID ...` and `RUN_STATE ...`

Current DEV smoke benchmark note:

```bash
.venv/bin/python3 run_bitgn_task.py start-run --task-id t01-t48 --benchmark-id bitgn/ecom1-dev
```

As of 2026-05-27, `bitgn/ecom1-dev` reports `t01-t48`. The competition
benchmark can start at `t00`; use the benchmark's actual task ids.

Debug plumbing check:

```bash
.venv/bin/python3 run_bitgn_task.py run-tasks --run-id latest --task-id t07 --workers 1 -d
```

In `-d` mode no LLM pipeline is used; the worker starts the trial and submits a
fixed denial. Use it only for log/debug inspection.

Legacy one-shot mode still exists:

```bash
.venv/bin/python3 run_bitgn_task.py --task-id t08 --benchmark-id bitgn/ecom1-dev
.venv/bin/python3 run_bitgn_task.py --task-id t00,t03,t100 --benchmark-id <published-ecom-benchmark-id> --workers 4
.venv/bin/python3 run_bitgn_task.py --task-id t00-t05 --benchmark-id <published-ecom-benchmark-id> --workers 4
```

One-shot mode starts a BitGN run, executes the selected tasks, then submits that
run in the old style. The staged lifecycle is preferred for competition work.

## Logs And State

Durable run orchestration state:

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

## Main Files

- `run_bitgn_task.py` - BitGN runner with staged lifecycle and legacy one-shot mode
- `ecom_runtime.py` - ECOM runtime adapter exposed to executed Python as `bitgn`
- `plan_repl_agent.py` - local single-task workspace runner
- `plan_agent/run_agent.py` - plan/step loop
- `plan_agent/run_step.py` - per-step Python REPL loop
- `plan_agent/prompt_agent.py` - ECOM tool/safety prompt
- `plan_agent/response.py` - final `message`, `outcome`, `refs` decision
- `bitgn/` - generated protobuf modules and small ConnectRPC clients
