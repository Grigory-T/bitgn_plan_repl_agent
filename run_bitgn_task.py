#!/usr/bin/env python3

import argparse
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.dont_write_bytecode = True


MAX_ATTEMPTS = 2


def _score_text(score: float | None) -> str:
    return "none" if score is None else f"{score:.2f}"


def _duration_text(seconds: float) -> str:
    total_seconds = max(0, int(round(seconds)))
    minutes, secs = divmod(total_seconds, 60)
    hours, mins = divmod(minutes, 60)
    if hours:
        return f"{hours}h {mins}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one or more BitGN PAC1 tasks end-to-end.")
    parser.add_argument(
        "--task-id",
        required=True,
        help="Task spec: one task (`t04` or `4`), comma list (`t01,t03,8`), or inclusive range (`1-5` or `t01-t05`)",
    )
    parser.add_argument(
        "--benchmark-id",
        default="bitgn/pac1-dev",
        help="BitGN benchmark id",
    )
    parser.add_argument(
        "--benchmark-host",
        default=os.getenv("BENCHMARK_HOST", "https://api.bitgn.com"),
        help="BitGN API host",
    )
    parser.add_argument(
        "-d",
        "--debug-preflight-deny",
        action="store_true",
        help="Force preflight to deny so logs can be inspected without running the full agent flow",
    )
    parser.add_argument(
        "--worker-mode",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--batch-id",
        help=argparse.SUPPRESS,
    )
    return parser


def _task_num(raw: str) -> int:
    value = raw.strip().lower()
    match = re.fullmatch(r"t?(\d+)", value)
    if not match:
        raise ValueError(f"Invalid task id: {raw}")
    return int(match.group(1))


def _task_id(num: int) -> str:
    return f"t{num:02d}"


def parse_task_spec(task_spec: str) -> list[str]:
    task_ids: list[str] = []
    seen: set[str] = set()

    for part in [item.strip() for item in task_spec.split(",") if item.strip()]:
        if "-" in part:
            left, right = [item.strip() for item in part.split("-", 1)]
            start = _task_num(left)
            end = _task_num(right)
            if start > end:
                raise ValueError(f"Invalid task range: {part}")
            nums = range(start, end + 1)
        else:
            nums = [_task_num(part)]

        for num in nums:
            task_id = _task_id(num)
            if task_id not in seen:
                seen.add(task_id)
                task_ids.append(task_id)

    if not task_ids:
        raise ValueError("No task ids parsed from --task-id")

    return task_ids


def _task_log_dir(task_id: str, batch_id: str):
    from plan_agent.log import _init_log_dir

    return _init_log_dir(task_id=task_id, batch_id=batch_id)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def _append_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(content.rstrip() + "\n")


def _write_runner_state(
    log_dir: Path,
    *,
    batch_id: str,
    task_id: str,
    benchmark_id: str,
    attempt: int,
    status: str,
    started_at: str | None = None,
    finished_at: str | None = None,
    trial_id: str | None = None,
    harness_url: str | None = None,
    runner_exit: int | None = None,
    elapsed_seconds: float | None = None,
    score: float | None = None,
    score_details: list[str] | None = None,
) -> None:
    lines = [
        "Batch ID",
        batch_id,
        "",
        "Task ID",
        task_id,
        "",
        "Benchmark ID",
        benchmark_id,
        "",
        "Attempt",
        str(attempt),
        "",
        "Status",
        status,
        "",
        "Started At",
        started_at or "(not set)",
        "",
        "Finished At",
        finished_at or "(not set)",
        "",
        "Trial ID",
        trial_id or "(not set)",
        "",
        "Harness URL",
        harness_url or "(not set)",
        "",
        "Runner Exit",
        "(not set)" if runner_exit is None else str(runner_exit),
        "",
        "Elapsed",
        "(not set)" if elapsed_seconds is None else _duration_text(elapsed_seconds),
        "",
        "Score",
        _score_text(score),
        "",
        "Score Details",
    ]

    if score_details:
        lines.extend(score_details)
    else:
        lines.append("(none)")

    _write_text(log_dir / "runner_state.txt", "\n".join(lines))


def _append_attempt(log_dir: Path, *, attempt: int, event: str, details: str) -> None:
    lines = [
        f"Attempt {attempt}",
        f"Event: {event}",
        "Details:",
        details.strip() or "(none)",
        "",
    ]
    _append_text(log_dir / "attempts.txt", "\n".join(lines))


def write_task_result(
    log_dir: Path,
    *,
    task_id: str,
    benchmark_id: str,
    trial_id: str | None,
    task: str,
    harness_url: str | None,
    elapsed_seconds: float,
    runner_exit: int,
    agent_result: str,
    final_response: str,
    outcome: str,
    refs: list[str],
) -> None:
    lines = [
        "Task ID",
        task_id,
        "",
        "Benchmark ID",
        benchmark_id,
        "",
        "Trial ID",
        trial_id or "(not set)",
        "",
        "Task",
        task.strip(),
        "",
        "BitGN Harness URL",
        harness_url or "(not set)",
        "",
        "Runner Exit",
        str(runner_exit),
        "",
        "Elapsed",
        _duration_text(elapsed_seconds),
        "",
        "Agent Result",
        agent_result.strip(),
        "",
        "Final Response",
        final_response.strip(),
        "",
        "Final Outcome",
        outcome.strip(),
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

    _write_text(log_dir / "task_result.txt", "\n".join(lines))


def record_bitgn_evaluation(log_dir: Path, *, trial_id: str | None, score: float | None, details: list[str]) -> None:
    score_text = _score_text(score)
    evaluation_lines = [
        "Trial ID",
        trial_id or "(not set)",
        "",
        "Score",
        score_text,
        "",
        "Details",
    ]
    if details:
        evaluation_lines.extend(details)
    else:
        evaluation_lines.append("(none)")

    evaluation_text = "\n".join(evaluation_lines)
    _write_text(log_dir / "bitgn_evaluation.txt", evaluation_text)

    task_result_path = log_dir / "task_result.txt"
    if task_result_path.exists():
        existing = task_result_path.read_text(encoding="utf-8").rstrip()
        marker = "BitGN Evaluation\npending"
        if marker in existing:
            updated = existing.replace(marker, "BitGN Evaluation\n" + evaluation_text, 1)
        else:
            updated = existing + "\n\nBitGN Evaluation\n" + evaluation_text
        _write_text(task_result_path, updated)


def _run_one_attempt(
    *,
    task_id: str,
    benchmark_id: str,
    benchmark_host: str,
    debug_preflight_deny: bool,
    batch_id: str,
    attempt: int,
) -> int:
    from bitgn_sdk.harness_connect import HarnessServiceClientSync
    from bitgn_sdk.harness_pb2 import EndTrialRequest, StartPlaygroundRequest
    from plan_agent.executor import initialize_runtime_globals, reset_persistent_globals
    from plan_agent.response import decide_response
    from plan_agent.run_agent import run_agent
    import bitgn_runtime

    log_dir = _task_log_dir(task_id, batch_id)
    started_at = datetime.now().isoformat(timespec="seconds")
    started_monotonic = time.monotonic()
    _write_runner_state(
        log_dir,
        batch_id=batch_id,
        task_id=task_id,
        benchmark_id=benchmark_id,
        attempt=attempt,
        status="running",
        started_at=started_at,
    )

    client = HarnessServiceClientSync(benchmark_host)
    trial = None
    task_text = ""
    harness_url = None
    agent_result = ""
    final_message = ""
    final_outcome = "OUTCOME_ERR_INTERNAL"
    final_refs: list[str] = []
    proc_returncode = 0
    score = None
    score_details: list[str] = []

    try:
        trial = client.start_playground(
            StartPlaygroundRequest(
                benchmark_id=benchmark_id,
                task_id=task_id,
            )
        )
        task_text = trial.instruction
        harness_url = trial.harness_url
        _append_attempt(
            log_dir,
            attempt=attempt,
            event="start_playground",
            details=f"trial_id={trial.trial_id}\nharness_url={trial.harness_url}",
        )

        os.environ["BITGN_HARNESS_URL"] = trial.harness_url
        if debug_preflight_deny:
            os.environ["BITGN_DEBUG_PREFLIGHT_DENY"] = "1"
        else:
            os.environ.pop("BITGN_DEBUG_PREFLIGHT_DENY", None)

        reset_persistent_globals()
        initialize_runtime_globals()
        bitgn_runtime.reset()
        bitgn_runtime.configure(trial.harness_url)

        agent_result, _, step_results = run_agent(
            trial.instruction,
            task_id=task_id,
            batch_id=batch_id,
        )
        response = decide_response(
            task=trial.instruction,
            agent_answer=agent_result,
            step_results=step_results,
            log_dir=str(log_dir),
        )
        final_message = response.message
        final_outcome = response.outcome
        final_refs = response.refs

        (log_dir / "final_response.txt").write_text(final_message.rstrip() + "\n", encoding="utf-8")

        if response.should_submit_to_bitgn:
            bitgn_runtime.answer(final_message, final_outcome, final_refs)

    except Exception as exc:
        proc_returncode = 1
        agent_result = f"Runner error: {exc}"
        final_message = f"Internal runner error: {exc}"
        final_outcome = "OUTCOME_ERR_INTERNAL"
        final_refs = []
        _append_attempt(
            log_dir,
            attempt=attempt,
            event="error",
            details=agent_result,
        )
        if trial is not None:
            try:
                bitgn_runtime.answer(final_message, final_outcome, final_refs)
            except Exception as submit_exc:
                _append_attempt(
                    log_dir,
                    attempt=attempt,
                    event="internal_error_submit_failed",
                    details=str(submit_exc),
                )
    finally:
        elapsed_seconds = time.monotonic() - started_monotonic
        if trial is not None:
            try:
                result = client.end_trial(EndTrialRequest(trial_id=trial.trial_id))
                score = result.score if result.HasField("score") else None
                score_details = list(result.score_detail)
            except Exception as end_exc:
                proc_returncode = 1
                score_details = [f"end_trial failed: {end_exc}"]
                _append_attempt(
                    log_dir,
                    attempt=attempt,
                    event="end_trial_failed",
                    details=str(end_exc),
                )

        write_task_result(
            log_dir,
            task_id=task_id,
            benchmark_id=benchmark_id,
            trial_id=trial.trial_id if trial is not None else None,
            task=task_text or task_id,
            harness_url=harness_url,
            elapsed_seconds=elapsed_seconds,
            runner_exit=proc_returncode,
            agent_result=agent_result or "(none)",
            final_response=final_message or "(none)",
            outcome=final_outcome,
            refs=final_refs,
        )
        record_bitgn_evaluation(
            log_dir,
            trial_id=trial.trial_id if trial is not None else None,
            score=score,
            details=score_details,
        )
        _write_runner_state(
            log_dir,
            batch_id=batch_id,
            task_id=task_id,
            benchmark_id=benchmark_id,
            attempt=attempt,
            status="completed" if proc_returncode == 0 else "errored",
            started_at=started_at,
            finished_at=datetime.now().isoformat(timespec="seconds"),
            trial_id=trial.trial_id if trial is not None else None,
            harness_url=harness_url,
            runner_exit=proc_returncode,
            elapsed_seconds=elapsed_seconds,
            score=score,
            score_details=score_details,
        )

    return proc_returncode


def _worker_main(args: argparse.Namespace) -> int:
    task_ids = parse_task_spec(args.task_id)
    if len(task_ids) != 1:
        raise ValueError("--worker-mode requires exactly one task id")

    task_id = task_ids[0]
    batch_id = args.batch_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = _task_log_dir(task_id, batch_id)

    last_returncode = 1
    for attempt in range(1, MAX_ATTEMPTS + 1):
        returncode = _run_one_attempt(
            task_id=task_id,
            benchmark_id=args.benchmark_id,
            benchmark_host=args.benchmark_host,
            debug_preflight_deny=args.debug_preflight_deny,
            batch_id=batch_id,
            attempt=attempt,
        )
        last_returncode = returncode
        if returncode == 0:
            return 0
        if attempt < MAX_ATTEMPTS:
            _append_attempt(
                log_dir,
                attempt=attempt,
                event="retry_scheduled",
                details=f"retrying task after runner error; next_attempt={attempt + 1}",
            )

    return last_returncode


def _spawn_worker(script_path: Path, args: argparse.Namespace, task_id: str, batch_id: str) -> subprocess.Popen:
    cmd = [
        sys.executable,
        str(script_path),
        "--worker-mode",
        "--task-id",
        task_id,
        "--benchmark-id",
        args.benchmark_id,
        "--benchmark-host",
        args.benchmark_host,
        "--batch-id",
        batch_id,
    ]
    if args.debug_preflight_deny:
        cmd.append("--debug-preflight-deny")

    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    return subprocess.Popen(
        cmd,
        cwd=str(script_path.parent),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _parent_main(args: argparse.Namespace) -> int:
    task_ids = parse_task_spec(args.task_id)
    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    script_path = Path(__file__).resolve()

    processes = [_spawn_worker(script_path, args, task_id, batch_id) for task_id in task_ids]
    exit_codes = [process.wait() for process in processes]
    return max(exit_codes, default=0)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.worker_mode:
        return _worker_main(args)
    return _parent_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
