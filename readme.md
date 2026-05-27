# plan_repl_agent ECOM

BitGN ECOM1 agent based on the reusable `general_purpose` plan/repl branch.

## What This Branch Is

This branch keeps the plan/repl architecture and connects it to the ECOM runtime:

- plan creation and replanning
- per-step Python execution
- BitGN ECOM runtime helper preloaded as `bitgn`
- deterministic submission of `message`, `outcome`, and `refs`
- local logs per trial

The ECOM runtime exposes a file-shaped commerce OS with tools such as
`tree`, `read`, `search`, `write`, `delete`, `stat`, `exec`, and `/bin/sql`.

## Setup

`.env` should contain:

```bash
OPENROUTER_API_KEY=...
BITGN_API_KEY=...
```

Install dependencies:

```bash
./setup_venv.sh
```

The public Buf wheels referenced by the sample agent were returning 403 from
this environment, so this repo vendors locally generated protobuf modules under
`bitgn/` from the public sample-agent protos.

## Run

List DEV task ids:

```bash
.venv/bin/python run_bitgn_task.py --list-tasks
```

Run one DEV task inside an unsubmitted selected-task run:

```bash
.venv/bin/python run_bitgn_task.py --task-id t01
```

Run a DEV subset inside an unsubmitted selected-task run:

```bash
.venv/bin/python run_bitgn_task.py --task-id t01-t05
```

Selected-task runs are not submitted by default because ECOM DEV does not expose
`StartPlayground`; this avoids accidentally submitting a partial low-score run.
Use `--submit-selected` only when you intentionally want to force-submit it.

Run a full leaderboard benchmark:

```bash
.venv/bin/python run_bitgn_task.py --benchmark-id bitgn/ecom1-dev
```

For the blind competition benchmark, switch only `--benchmark-id` to the
published production id when BitGN opens it.

## Main Files

- `run_bitgn_task.py` - BitGN harness runner
- `ecom_runtime.py` - ECOM runtime adapter exposed to executed Python as `bitgn`
- `plan_repl_agent.py` - local single-task workspace runner
- `plan_agent/run_agent.py` - plan/step loop
- `plan_agent/run_step.py` - per-step Python REPL loop
- `plan_agent/prompt_agent.py` - ECOM tool/safety prompt
- `bitgn/` - generated protobuf modules and small ConnectRPC clients

## Logs

Trial logs are written under:

```bash
logs/<batch_id>/<task_id>/
```

Each task directory includes planner logs, step logs, response prompt, and
`runner_result.json`.
