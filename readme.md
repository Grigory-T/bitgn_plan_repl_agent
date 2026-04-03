# plan_repl_agent

BitGN sandbox agent.

## Workflow

- laptop: source of truth and Git repo
- `bitgn`: execution machine only, no Git metadata

Edit locally in:

```bash
/home/linuxuser/bitgn/plan_repl_agent
```

Sync to `bitgn`:

```bash
/home/linuxuser/bitgn/sync-plan-agent.sh
```

That syncs the project to `bitgn` and runs a remote syntax check.

## Run

On `bitgn`:

```bash
cd ~/bitgn/plan_repl_agent
./setup_venv.sh
.venv/bin/python3 run_bitgn_task.py --task-id t04
```

Examples:

```bash
.venv/bin/python3 run_bitgn_task.py --task-id t08
.venv/bin/python3 run_bitgn_task.py --task-id t01,t03,t05
.venv/bin/python3 run_bitgn_task.py --task-id t01-t05
```

## Main Files

- `run_bitgn_task.py`: BitGN launcher
- `setup_venv.sh`: shared remote `.venv` setup
- `plan_agent/`: planner, step loop, response phase, prompts
- `bitgn_runtime.py`: BitGN mini-runtime wrapper
- `bitgn_sdk/`: generated mini-runtime client
- `logs/`: run logs
- `work/`: temporary run directories

## Notes

- `.env` is local and synced to `bitgn`, but ignored by Git
- `logs/` and `work/` are ignored by Git
- run artifacts are analyzed on `bitgn`
