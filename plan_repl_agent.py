#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from plan_agent.executor import initialize_runtime_globals, reset_persistent_globals
from plan_agent.response import decide_response
from plan_agent.run_agent import run_agent


load_dotenv()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the planning agent against a fresh local workspace.")
    parser.add_argument("task", help="Task to solve")
    parser.add_argument(
        "--runs-root",
        default=str(Path(__file__).resolve().parent / "runs"),
        help="Root directory for per-run workspaces and logs",
    )
    return parser


def _run_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    run_id = _run_id()
    run_root = Path(args.runs_root).expanduser().resolve() / run_id
    workspace_root = run_root / "workspace"
    logs_root = run_root / "step_logs"

    workspace_root.mkdir(parents=True, exist_ok=True)
    logs_root.mkdir(parents=True, exist_ok=True)

    os.environ["PLAN_REPL_LOG_ROOT"] = str(logs_root)
    os.environ["PLAN_REPL_WORKSPACE_ROOT"] = str(workspace_root)

    (run_root / "task.txt").write_text(args.task.rstrip() + "\n", encoding="utf-8")

    reset_persistent_globals()
    initialize_runtime_globals()

    agent_answer, log_dir, step_results = run_agent(task=args.task)
    response = decide_response(
        task=args.task,
        agent_answer=agent_answer,
        step_results=step_results,
        log_dir=log_dir,
    )

    result_payload = {
        "task": args.task,
        "message": response.message,
        "reasoning": response.reasoning,
        "workspace_root": str(workspace_root),
        "log_dir": log_dir,
    }
    (run_root / "result.json").write_text(json.dumps(result_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (run_root / "final_answer.txt").write_text(response.message.rstrip() + "\n", encoding="utf-8")

    print(f"RUN_ID {run_id}")
    print(f"RUN_ROOT {run_root}")
    print(f"WORKSPACE_ROOT {workspace_root}")
    print(f"LOG_DIR {log_dir}")
    print("")
    print(response.message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
