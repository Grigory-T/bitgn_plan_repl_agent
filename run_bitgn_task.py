#!/usr/bin/env python3

import os
import sys
import shutil
import uuid
from pathlib import Path
import argparse


os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.dont_write_bytecode = True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one BitGN sandbox task end-to-end.")
    parser.add_argument("--task-id", required=True, help="BitGN task id, for example t04")
    parser.add_argument(
        "--benchmark-id",
        default="bitgn/sandbox",
        help="BitGN benchmark id",
    )
    parser.add_argument(
        "--benchmark-host",
        default=os.getenv("BENCHMARK_HOST", "https://api.bitgn.com"),
        help="BitGN API host",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Preserve existing logs and work before starting the run",
    )
    return parser


def clear_directories(project: Path) -> None:
    for dir_name in ("logs", "work"):
        dir_path = project / dir_name
        if not dir_path.exists():
            continue
        for item in dir_path.iterdir():
            try:
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            except FileNotFoundError:
                pass


def create_run_dir(project: Path) -> Path:
    run_id = uuid.uuid4().hex[:12]
    run_dir = project / "work" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def write_task_result(
    log_dir: Path,
    *,
    task: str,
    harness_url: str | None,
    agent_result: str,
    final_response: str,
    refs: list[str],
) -> None:
    lines = [
        "Task",
        task.strip(),
        "",
        "BitGN Harness URL",
        harness_url or "(not set)",
        "",
        "Agent Result",
        agent_result.strip(),
        "",
        "Final Response",
        final_response.strip(),
        "",
        "Final Refs",
    ]

    if refs:
        lines.extend(refs)
    else:
        lines.append("(none)")

    lines.extend([
        "",
        "BitGN Evaluation",
        "pending",
    ])

    (log_dir / "task_result.txt").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def record_bitgn_evaluation(log_dir: Path, *, trial_id: str, score: str, details: list[str]) -> None:
    evaluation_lines = [
        "Trial ID",
        trial_id,
        "",
        "Score",
        score,
        "",
        "Details",
    ]
    if details:
        evaluation_lines.extend(details)
    else:
        evaluation_lines.append("(none)")

    evaluation_text = "\n".join(evaluation_lines).rstrip() + "\n"
    (log_dir / "bitgn_evaluation.txt").write_text(evaluation_text, encoding="utf-8")

    task_result_path = log_dir / "task_result.txt"
    if task_result_path.exists():
        existing = task_result_path.read_text(encoding="utf-8").rstrip()
        marker = "BitGN Evaluation\npending"
        if marker in existing:
            updated = existing.replace(marker, "BitGN Evaluation\n" + evaluation_text.rstrip(), 1)
        else:
            updated = existing + "\n\nBitGN Evaluation\n" + evaluation_text.rstrip()
    else:
        updated = "\n".join([
            "Task",
            "(missing)",
            "",
            "BitGN Harness URL",
            "(missing)",
            "",
            "Agent Result",
            "(missing)",
            "",
            "Final Response",
            "(missing)",
            "",
            "Final Refs",
            "(none)",
            "",
            "BitGN Evaluation",
            evaluation_text.rstrip(),
        ])

    task_result_path.write_text(updated.rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    project = Path(__file__).resolve().parent
    sample_agents = Path.home() / "bitgn" / "sample-agents" / "sandbox-py"
    if str(sample_agents) not in sys.path:
        sys.path.insert(0, str(sample_agents))

    from bitgn.harness_connect import HarnessServiceClientSync
    from bitgn.harness_pb2 import EndTrialRequest, StartPlaygroundRequest
    from plan_agent.executor import initialize_runtime_globals, reset_persistent_globals
    from plan_agent.response import decide_response
    from plan_agent.run_agent import run_agent
    import bitgn_runtime

    if not args.no_clean:
        clear_directories(project)

    client = HarnessServiceClientSync(args.benchmark_host)

    trial = client.start_playground(
        StartPlaygroundRequest(
            benchmark_id=args.benchmark_id,
            task_id=args.task_id,
        )
    )

    print(f"TASK {args.task_id}")
    print(f"TRIAL_ID {trial.trial_id}")
    print("INSTRUCTION_START")
    print(trial.instruction)
    print("INSTRUCTION_END")
    print(f"HARNESS_URL {trial.harness_url}")
    print("RUNNER_START")

    before = {p.name for p in (project / "logs").iterdir() if p.is_dir()} if (project / "logs").exists() else set()

    env = os.environ.copy()
    env["BITGN_HARNESS_URL"] = trial.harness_url
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    os.environ["BITGN_HARNESS_URL"] = trial.harness_url
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

    reset_persistent_globals()
    initialize_runtime_globals()

    run_dir = create_run_dir(project)
    original_cwd = Path.cwd()
    log_dir = None
    proc_returncode = 0

    print(f"Run directory: {run_dir}", flush=True)

    try:
        os.chdir(run_dir)
        agent_result, log_dir, step_results = run_agent(trial.instruction)
    except Exception as exc:
        agent_result = f"Runner error: {exc}"
        proc_returncode = 1
        step_results = []
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(run_dir, ignore_errors=True)

    response = decide_response(
        task=trial.instruction,
        agent_answer=agent_result,
        step_results=step_results,
        log_dir=log_dir,
    )

    if log_dir:
        log_dir_path = Path(log_dir)
        (log_dir_path / "final_response.txt").write_text(response.message.rstrip() + "\n", encoding="utf-8")
        write_task_result(
            log_dir_path,
            task=trial.instruction,
            harness_url=trial.harness_url,
            agent_result=agent_result,
            final_response=response.message,
            refs=response.refs,
        )

    if response.should_submit_to_bitgn:
        bitgn_runtime.answer(response.message, response.refs)

    print("\n=== Agent Result ===", flush=True)
    print(agent_result, flush=True)
    print("\n=== Final Response ===", flush=True)
    print(response.message, flush=True)
    if response.refs:
        print("\n=== Final Refs ===", flush=True)
        for ref in response.refs:
            print(ref, flush=True)

    print(f"RUNNER_EXIT {proc_returncode}", flush=True)
    print("RUNNER_END", flush=True)

    after = {p.name for p in (project / "logs").iterdir() if p.is_dir()} if (project / "logs").exists() else set()
    new_logs = sorted(after - before)

    result = client.end_trial(EndTrialRequest(trial_id=trial.trial_id))
    score = result.score if result.HasField("score") else None
    print(f"SCORE {score}")
    for item in result.score_detail:
        print(f"DETAIL {item}")

    print("LOG_DIRS_START")
    for log_dir in new_logs:
        log_path = project / "logs" / log_dir
        print(str(log_path))
        record_bitgn_evaluation(
            log_path,
            trial_id=trial.trial_id,
            score=str(score),
            details=list(result.score_detail),
        )
    print("LOG_DIRS_END")

    return 0 if proc_returncode == 0 else proc_returncode


if __name__ == "__main__":
    raise SystemExit(main())
