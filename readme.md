# plan_repl_agent

BitGN PAC1 agent.

## USER

### What This Repo Is

This repo is the editable agent implementation.
It is developed locally in:

```bash
/home/linuxuser/bitgn/plan_repl_agent
```

It is then synced to the `bitgn` machine for execution.

### Prerequisites

- `.env` created from `.env.sample`
- provider keys configured in `.env`
- reachable `bitgn` machine
- working `sample-agents` folder in:

```bash
/home/linuxuser/bitgn/sample-agents
```

### Local Sync To `bitgn`

From the local machine:

```bash
cd /home/linuxuser/bitgn
./sync-plan-agent.sh
```

This syncs:

- `plan_repl_agent/`
- `sample-agents/`
- `erc3-prod-key-concept-score-67/`

and then runs a remote syntax check on `bitgn`.

### Run On `bitgn`

```bash
ssh bitgn
cd ~/bitgn/plan_repl_agent
./setup_venv.sh
.venv/bin/python3 run_bitgn_task.py --task-id t01 --benchmark-id bitgn/pac1-dev
```

Useful examples:

```bash
.venv/bin/python3 run_bitgn_task.py --task-id t08 --benchmark-id bitgn/pac1-dev
.venv/bin/python3 run_bitgn_task.py --task-id t01,t03,t05 --benchmark-id bitgn/pac1-dev
.venv/bin/python3 run_bitgn_task.py --task-id t01-t05 --benchmark-id bitgn/pac1-dev
```

### Logs

Run logs are written on `bitgn` under:

```bash
~/bitgn/plan_repl_agent/logs/
```

## TECH

### Current Runtime Model

This repo now targets PAC1 only.
Old sandbox-runtime compatibility is intentionally not preserved.

Control plane:

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
  Main launcher. Spawns one worker process per task, runs each task independently, retries runner errors once per task, submits the final answer, and records task-local evaluation logs.

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
  Includes PCM protobuf/connect files required by the current PAC1 path.

- [setup_venv.sh](/home/linuxuser/bitgn/plan_repl_agent/setup_venv.sh)
  Installs Python dependencies into the repo-local `.venv`.

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

Validated on `bitgn`:

- sync works
- remote syntax check works
- PAC1 task execution works
- `t01` scored `1.00` on `bitgn/pac1-dev`

### Notes

- `.env` is ignored by Git
- `.venv/` is ignored by Git
- `logs/` is ignored by Git
- `sample-agents` should be treated as an external reference/source repo, not as the main place for local edits
