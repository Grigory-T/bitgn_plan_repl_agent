#!/usr/bin/env python3

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv


os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.dont_write_bytecode = True
load_dotenv()


LEADERBOARD_RUN_NAME = "key_concept:plan_repl_agent"
DEFAULT_WORKERS = 10
RUNS_DIR = Path(__file__).resolve().parent / "runs"
RUN_PREPARE_TIMEOUT_SECONDS = 60
RUN_PREPARE_POLL_SECONDS = 0.5


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


def _proto_text(value, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _proto_list(value) -> list:
    if value is None:
        return []
    try:
        return list(value)
    except TypeError:
        return []


def _safe_score(response) -> float | None:
    try:
        if hasattr(response, "HasField") and response.HasField("score"):
            return float(response.score)
    except Exception:
        pass
    value = getattr(response, "score", None)
    if value in (None, ""):
        return None
    try:
        return float(value)
    except Exception:
        return None


def _safe_score_details(response) -> list[str]:
    try:
        return [str(item) for item in _proto_list(getattr(response, "score_detail", [])) if str(item).strip()]
    except Exception:
        return []


def _extract_trial_payload(trial, fallback_task_id: str) -> dict[str, str]:
    return {
        "trial_id": _proto_text(getattr(trial, "trial_id", None)),
        "task_id": _proto_text(getattr(trial, "task_id", None), fallback_task_id),
        "instruction": _proto_text(getattr(trial, "instruction", None)),
        "harness_url": _proto_text(getattr(trial, "harness_url", None)),
        "run_id": _proto_text(getattr(trial, "run_id", None)),
        "benchmark_id": _proto_text(getattr(trial, "benchmark_id", None)),
    }


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
    parser.add_argument(
        "--trial-id",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"Maximum number of task worker processes to run in parallel (default: {DEFAULT_WORKERS})",
    )
    return parser


def build_lifecycle_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage BitGN PAC1 leaderboard runs in separate stages.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("start-run", help="Create a leaderboard run and store local run state")
    start_parser.add_argument(
        "--task-id",
        required=True,
        help="Task spec: one task (`t04` or `4`), comma list (`t01,t03,8`), or inclusive range (`1-5` or `t01-t05`)",
    )
    start_parser.add_argument(
        "--benchmark-id",
        default="bitgn/pac1-dev",
        help="BitGN benchmark id",
    )
    start_parser.add_argument(
        "--benchmark-host",
        default=os.getenv("BENCHMARK_HOST", "https://api.bitgn.com"),
        help="BitGN API host",
    )

    run_parser = subparsers.add_parser("run-tasks", help="Run a subset of tasks for an existing leaderboard run")
    run_parser.add_argument("--run-id", required=True, help="Existing run id, or 'latest'")
    run_parser.add_argument(
        "--task-id",
        help="Optional task subset to run. If omitted, runs all tasks not yet completed locally.",
    )
    run_parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"Maximum number of task worker processes to run in parallel (default: {DEFAULT_WORKERS})",
    )
    run_parser.add_argument(
        "-d",
        "--debug-preflight-deny",
        action="store_true",
        help="Force preflight to deny so logs can be inspected without running the full agent flow",
    )

    end_parser = subparsers.add_parser("end-run", help="Submit a leaderboard run explicitly")
    end_parser.add_argument("--run-id", required=True, help="Existing run id, or 'latest'")

    status_parser = subparsers.add_parser("status", help="Show current local status for an existing leaderboard run")
    status_parser.add_argument("--run-id", required=True, help="Existing run id, or 'latest'")

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


def _batch_log_dir(batch_id: str):
    from plan_agent.log import _init_log_dir

    return _init_log_dir(batch_id=batch_id)


def _run_dir(run_id: str) -> Path:
    return RUNS_DIR / run_id


def _run_state_path(run_id: str) -> Path:
    return _run_dir(run_id) / "run_state.json"


def _latest_run_path() -> Path:
    return RUNS_DIR / "latest_run.txt"


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def _append_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(content.rstrip() + "\n")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_run_id(run_id: str) -> str:
    if run_id != "latest":
        return run_id
    latest_path = _latest_run_path()
    if not latest_path.exists():
        raise FileNotFoundError("No latest run recorded.")
    return latest_path.read_text(encoding="utf-8").strip()


def _load_run_state(run_id: str) -> dict:
    resolved_run_id = _resolve_run_id(run_id)
    path = _run_state_path(resolved_run_id)
    if not path.exists():
        raise FileNotFoundError(f"Run state not found: {path}")
    payload = _read_json(path)
    payload["run_id"] = resolved_run_id
    return payload


def _save_run_state(state: dict) -> None:
    run_id = state["run_id"]
    _write_json(_run_state_path(run_id), state)
    _write_text(_latest_run_path(), run_id)


def _human_started_at() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _print_command_started() -> None:
    print(f"STARTED_AT {_human_started_at()}")


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


def _bitgn_api_key() -> str:
    return (os.getenv("BITGN_API_KEY") or "").strip()


def _leaderboard_mode_enabled() -> bool:
    return bool(_bitgn_api_key())


def _parse_task_result_summary(task_dir: Path) -> dict:
    summary = {
        "runner_exit": None,
        "outcome": None,
        "score": None,
        "details": [],
    }
    task_result_path = task_dir / "task_result.txt"
    if task_result_path.exists():
        section = None
        for raw_line in task_result_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line == "Runner Exit":
                section = "runner_exit"
                continue
            if line == "Final Outcome":
                section = "outcome"
                continue
            if section == "runner_exit":
                try:
                    summary["runner_exit"] = int(line)
                except ValueError:
                    summary["runner_exit"] = None
                section = None
                continue
            if section == "outcome":
                summary["outcome"] = line
                section = None
                continue

    evaluation_path = task_dir / "bitgn_evaluation.txt"
    if evaluation_path.exists():
        section = None
        for raw_line in evaluation_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line == "Score":
                section = "score"
                continue
            if line == "Details":
                section = "details"
                continue
            if line == "Trial ID":
                section = None
                continue
            if section == "score":
                try:
                    summary["score"] = float(line)
                except ValueError:
                    summary["score"] = None
                section = None
                continue
            if section == "details":
                summary["details"].append(line)

    return summary


def _refresh_run_task_state(state: dict, task_id: str, batch_id: str) -> None:
    task_dir = _task_log_dir(task_id, batch_id)
    task_state = state["tasks"][task_id]
    parsed = _parse_task_result_summary(task_dir)
    task_state["last_batch_id"] = batch_id
    task_state["last_finished_at"] = datetime.now().isoformat(timespec="seconds")
    task_state["last_runner_exit"] = parsed["runner_exit"]
    task_state["last_outcome"] = parsed["outcome"]
    task_state["last_score"] = parsed["score"]
    task_state["last_details"] = parsed["details"]
    task_state["status"] = "completed" if parsed["runner_exit"] == 0 else "local_error"


def _run_one_attempt(
    *,
    task_id: str,
    benchmark_id: str,
    benchmark_host: str,
    debug_preflight_deny: bool,
    batch_id: str,
    attempt: int,
    trial_id: str | None = None,
) -> int:
    from bitgn_sdk.harness_connect import HarnessServiceClientSync
    from bitgn_sdk.harness_pb2 import EndTrialRequest, StartPlaygroundRequest, StartTrialRequest
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
    should_end_trial = False

    try:
        if trial_id:
            trial = client.start_trial(
                StartTrialRequest(trial_id=trial_id)
            )
            start_event = "start_trial"
        else:
            trial = client.start_playground(
                StartPlaygroundRequest(
                    benchmark_id=benchmark_id,
                    task_id=task_id,
                )
            )
            start_event = "start_playground"
        trial_payload = _extract_trial_payload(trial, task_id)
        task_text = trial_payload["instruction"] or task_id
        harness_url = trial_payload["harness_url"]
        effective_trial_id = trial_payload["trial_id"] or trial_id
        if not harness_url:
            raise RuntimeError("BitGN did not return harness_url for the started trial.")
        _append_attempt(
            log_dir,
            attempt=attempt,
            event=start_event,
            details=f"trial_id={effective_trial_id or '(missing)'}\nharness_url={harness_url}",
        )

        os.environ["BITGN_HARNESS_URL"] = harness_url
        if debug_preflight_deny:
            reset_persistent_globals()
            initialize_runtime_globals()
            bitgn_runtime.reset()
            bitgn_runtime.configure(harness_url)
            agent_result = "Request denied at preflight: Forced preflight denial for debug logging mode."
            final_message = "Request denied at preflight: Forced preflight denial for debug logging mode."
            final_outcome = "OUTCOME_DENIED_SECURITY"
            final_refs = []
            (log_dir / "final_response.txt").write_text(final_message + "\n", encoding="utf-8")
            bitgn_runtime.answer(final_message, final_outcome, final_refs)
            should_end_trial = True
            return proc_returncode

        if debug_preflight_deny:
            os.environ["BITGN_DEBUG_PREFLIGHT_DENY"] = "1"
        else:
            os.environ.pop("BITGN_DEBUG_PREFLIGHT_DENY", None)

        reset_persistent_globals()
        initialize_runtime_globals()
        bitgn_runtime.reset()
        bitgn_runtime.configure(harness_url)

        agent_result, _, step_results = run_agent(
            task_text,
            task_id=task_id,
            batch_id=batch_id,
        )
        response = decide_response(
            task=task_text,
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
        should_end_trial = True

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
    finally:
        elapsed_seconds = time.monotonic() - started_monotonic
        if trial is not None and should_end_trial:
            try:
                effective_trial_id = _proto_text(getattr(trial, "trial_id", None), trial_id or "")
                result = client.end_trial(EndTrialRequest(trial_id=effective_trial_id))
                score = _safe_score(result)
                score_details = _safe_score_details(result)
            except Exception as end_exc:
                proc_returncode = 1
                score_details = [f"end_trial failed: {end_exc}"]
                _append_attempt(
                    log_dir,
                    attempt=attempt,
                    event="end_trial_failed",
                    details=str(end_exc),
                )
        elif trial is not None and proc_returncode != 0:
            score_details = ["trial not ended; rerun manually"]
            _append_attempt(
                log_dir,
                attempt=attempt,
                event="trial_left_open",
                details="Runner failed before final submission; trial was left open for manual rerun.",
            )

        write_task_result(
            log_dir,
            task_id=task_id,
            benchmark_id=benchmark_id,
            trial_id=_proto_text(getattr(trial, "trial_id", None)) if trial is not None else None,
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
            trial_id=_proto_text(getattr(trial, "trial_id", None)) if trial is not None else None,
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
            trial_id=_proto_text(getattr(trial, "trial_id", None)) if trial is not None else None,
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
    return _run_one_attempt(
        task_id=task_id,
        benchmark_id=args.benchmark_id,
        benchmark_host=args.benchmark_host,
        debug_preflight_deny=args.debug_preflight_deny,
        batch_id=batch_id,
        attempt=1,
        trial_id=args.trial_id,
    )


def _spawn_worker(
    *,
    script_path: Path,
    task_id: str,
    batch_id: str,
    benchmark_id: str,
    benchmark_host: str,
    debug_preflight_deny: bool,
    trial_id: str | None = None,
) -> subprocess.Popen:
    cmd = [
        sys.executable,
        str(script_path),
        "--worker-mode",
        "--task-id",
        task_id,
        "--benchmark-id",
        benchmark_id,
        "--benchmark-host",
        benchmark_host,
        "--batch-id",
        batch_id,
    ]
    if trial_id:
        cmd.extend(["--trial-id", trial_id])
    if debug_preflight_deny:
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


def _task_trial_map_for_run(benchmark_host: str, benchmark_id: str, task_ids: list[str], api_key: str, batch_id: str) -> tuple[str, dict[str, str]]:
    from bitgn_sdk.harness_connect import HarnessServiceClientSync
    from bitgn_sdk.harness_pb2 import GetRunRequest, StartRunRequest

    client = HarnessServiceClientSync(benchmark_host)
    run = client.start_run(
        StartRunRequest(
            benchmark_id=benchmark_id,
            name=LEADERBOARD_RUN_NAME,
            api_key=api_key,
        )
    )
    run_id = _proto_text(getattr(run, "run_id", None))
    if not run_id:
        raise RuntimeError("BitGN did not return run_id from start_run.")

    deadline = time.monotonic() + RUN_PREPARE_TIMEOUT_SECONDS
    trial_map: dict[str, str] = {}
    while time.monotonic() < deadline:
        run_info = client.get_run(GetRunRequest(run_id=run_id))
        trial_map = {}
        for trial in _proto_list(getattr(run_info, "trials", [])):
            mapped_task_id = _proto_text(getattr(trial, "task_id", None))
            mapped_trial_id = _proto_text(getattr(trial, "trial_id", None))
            if mapped_task_id in task_ids and mapped_trial_id:
                trial_map[mapped_task_id] = mapped_trial_id
        missing = [task_id for task_id in task_ids if task_id not in trial_map]
        if not missing:
            return run_id, trial_map
        time.sleep(RUN_PREPARE_POLL_SECONDS)

    missing = [task_id for task_id in task_ids if task_id not in trial_map]
    raise RuntimeError(f"Timed out waiting for prepared trials for tasks: {', '.join(missing)}")


def _submit_run(benchmark_host: str, run_id: str) -> None:
    from bitgn_sdk.harness_connect import HarnessServiceClientSync
    from bitgn_sdk.harness_pb2 import SubmitRunRequest

    client = HarnessServiceClientSync(benchmark_host)
    client.submit_run(SubmitRunRequest(run_id=run_id, force=True))


def _force_submit_unfinished_tasks(state: dict) -> list[str]:
    from bitgn_sdk.harness_connect import HarnessServiceClientSync
    from bitgn_sdk.harness_pb2 import EndTrialRequest, StartTrialRequest
    import bitgn_runtime

    unfinished = [
        task_id
        for task_id in state["task_ids"]
        if state["tasks"][task_id]["status"] != "completed"
    ]
    if not unfinished:
        return []

    client = HarnessServiceClientSync(state["benchmark_host"])
    finalized: list[str] = []
    message = "Task was not completed during manual execution; submitting a conservative denial at end-run."
    timestamp = datetime.now().isoformat(timespec="seconds")

    for task_id in unfinished:
        task_state = state["tasks"][task_id]
        trial = client.start_trial(StartTrialRequest(trial_id=task_state["trial_id"]))
        trial_payload = _extract_trial_payload(trial, task_id)
        harness_url = trial_payload["harness_url"]
        effective_trial_id = trial_payload["trial_id"] or task_state["trial_id"]
        if not harness_url:
            raise RuntimeError(f"BitGN did not return harness_url while force-submitting {task_id}.")
        bitgn_runtime.reset()
        bitgn_runtime.configure(harness_url)
        bitgn_runtime.answer(message, "OUTCOME_DENIED_SECURITY", [])
        result = client.end_trial(EndTrialRequest(trial_id=effective_trial_id))

        task_state["status"] = "completed"
        task_state["last_started_at"] = task_state.get("last_started_at") or timestamp
        task_state["last_finished_at"] = timestamp
        task_state["last_runner_exit"] = 0
        task_state["last_outcome"] = "OUTCOME_DENIED_SECURITY"
        task_state["last_score"] = _safe_score(result)
        task_state["last_details"] = _safe_score_details(result)
        finalized.append(task_id)

    return finalized


def _write_batch_runner_state(
    batch_dir: Path,
    *,
    batch_id: str,
    benchmark_id: str,
    workers: int,
    mode: str,
    total_tasks: int,
    pending_tasks: list[str],
    running_tasks: list[str],
    finished_tasks: list[str],
    run_id: str | None = None,
) -> None:
    lines = [
        "Batch ID",
        batch_id,
        "",
        "Benchmark ID",
        benchmark_id,
        "",
        "Mode",
        mode,
        "",
        "Workers",
        str(workers),
        "",
        "Run ID",
        run_id or "(none)",
        "",
        "Total Tasks",
        str(total_tasks),
        "",
        "Pending Tasks",
    ]
    lines.extend(pending_tasks or ["(none)"])
    lines.extend([
        "",
        "Running Tasks",
    ])
    lines.extend(running_tasks or ["(none)"])
    lines.extend([
        "",
        "Finished Tasks",
    ])
    if finished_tasks:
        for task_id in finished_tasks:
            lines.append(_format_finished_task_summary(batch_dir, task_id))
    else:
        lines.append("(none)")
    _write_text(batch_dir / "batch_runner_state.txt", "\n".join(lines))


def _mark_interrupted_tasks(run_state: dict | None, active_task_ids: list[str], batch_id: str) -> None:
    if run_state is None:
        return
    timestamp = datetime.now().isoformat(timespec="seconds")
    for task_id in active_task_ids:
        task_state = run_state["tasks"][task_id]
        task_state["status"] = "pending"
        task_state["last_batch_id"] = batch_id
        task_state["last_finished_at"] = timestamp
        task_state["last_runner_exit"] = 130
        task_state["last_outcome"] = None
        task_state["last_score"] = None
        task_state["last_details"] = ["run-tasks interrupted locally; safe to rerun this task"]
    _save_run_state(run_state)


def _format_finished_task_summary(batch_dir: Path, task_id: str) -> str:
    task_dir = batch_dir / task_id
    evaluation_path = task_dir / "bitgn_evaluation.txt"
    if not evaluation_path.exists():
        return f"{task_id} | score=none | details=(pending)"

    score = "none"
    details: list[str] = []
    section = None
    for raw_line in evaluation_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line == "Score":
            section = "score"
            continue
        if line == "Details":
            section = "details"
            continue
        if line == "Trial ID":
            section = None
            continue
        if section == "score":
            score = line
            section = None
            continue
        if section == "details":
            details.append(line)

    details_text = "; ".join(details) if details else "(none)"
    return f"{task_id} | score={score} | details={details_text}"


def _run_worker_pool(
    *,
    script_path: Path,
    benchmark_id: str,
    benchmark_host: str,
    debug_preflight_deny: bool,
    workers: int,
    task_ids: list[str],
    batch_id: str,
    trial_map: dict[str, str],
    run_id: str | None,
    run_state: dict | None = None,
) -> int:
    batch_dir = _batch_log_dir(batch_id)
    worker_count = max(1, min(workers, len(task_ids)))
    pending_tasks = list(task_ids)
    active: list[tuple[str, subprocess.Popen]] = []
    exit_codes: dict[str, int] = {}

    _write_batch_runner_state(
        batch_dir,
        batch_id=batch_id,
        benchmark_id=benchmark_id,
        workers=worker_count,
        mode="leaderboard" if run_id else "playground",
        total_tasks=len(task_ids),
        pending_tasks=pending_tasks,
        running_tasks=[],
        finished_tasks=[],
        run_id=run_id,
    )

    try:
        while pending_tasks or active:
            while pending_tasks and len(active) < worker_count:
                task_id = pending_tasks.pop(0)
                if run_state is not None:
                    task_state = run_state["tasks"][task_id]
                    task_state["status"] = "running"
                    task_state["last_batch_id"] = batch_id
                    task_state["last_started_at"] = datetime.now().isoformat(timespec="seconds")
                    _save_run_state(run_state)
                process = _spawn_worker(
                    script_path=script_path,
                    task_id=task_id,
                    batch_id=batch_id,
                    benchmark_id=benchmark_id,
                    benchmark_host=benchmark_host,
                    debug_preflight_deny=debug_preflight_deny,
                    trial_id=trial_map.get(task_id),
                )
                active.append((task_id, process))

            still_active: list[tuple[str, subprocess.Popen]] = []
            for task_id, process in active:
                returncode = process.poll()
                if returncode is None:
                    still_active.append((task_id, process))
                    continue
                exit_codes[task_id] = returncode
                if run_state is not None:
                    _refresh_run_task_state(run_state, task_id, batch_id)
                    _save_run_state(run_state)
            active = still_active

            _write_batch_runner_state(
                batch_dir,
                batch_id=batch_id,
                benchmark_id=benchmark_id,
                workers=worker_count,
                mode="leaderboard" if run_id else "playground",
                total_tasks=len(task_ids),
                pending_tasks=pending_tasks,
                running_tasks=[task_id for task_id, _ in active],
                finished_tasks=list(exit_codes.keys()),
                run_id=run_id,
            )

            if pending_tasks or active:
                time.sleep(0.5)
    except KeyboardInterrupt:
        for _, process in active:
            try:
                process.terminate()
            except Exception:
                pass
        time.sleep(0.2)
        for _, process in active:
            if process.poll() is None:
                try:
                    process.kill()
                except Exception:
                    pass
        for _, process in active:
            try:
                process.wait(timeout=1)
            except Exception:
                pass
        interrupted_task_ids = [task_id for task_id, _ in active]
        _mark_interrupted_tasks(run_state, interrupted_task_ids, batch_id)
        _write_batch_runner_state(
            batch_dir,
            batch_id=batch_id,
            benchmark_id=benchmark_id,
            workers=worker_count,
            mode="leaderboard" if run_id else "playground",
            total_tasks=len(task_ids),
            pending_tasks=pending_tasks + interrupted_task_ids,
            running_tasks=[],
            finished_tasks=list(exit_codes.keys()),
            run_id=run_id,
        )
        print("INTERRUPTED Ctrl+C received; active workers stopped. Safe to rerun pending tasks.")
        return 130

    return max(exit_codes.values(), default=0)


def _parent_main(args: argparse.Namespace) -> int:
    task_ids = parse_task_spec(args.task_id)
    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    script_path = Path(__file__).resolve()
    run_id = None
    trial_map: dict[str, str] = {}

    if _leaderboard_mode_enabled():
        run_id, trial_map = _task_trial_map_for_run(
            benchmark_host=args.benchmark_host,
            benchmark_id=args.benchmark_id,
            task_ids=task_ids,
            api_key=_bitgn_api_key(),
            batch_id=batch_id,
        )

    try:
        return _run_worker_pool(
            script_path=script_path,
            benchmark_id=args.benchmark_id,
            benchmark_host=args.benchmark_host,
            debug_preflight_deny=args.debug_preflight_deny,
            workers=args.workers,
            task_ids=task_ids,
            batch_id=batch_id,
            trial_map=trial_map,
            run_id=run_id,
        )
    finally:
        if run_id:
            _submit_run(args.benchmark_host, run_id)


def _start_run_command(args: argparse.Namespace) -> int:
    _print_command_started()
    task_ids = parse_task_spec(args.task_id)
    api_key = _bitgn_api_key()
    if not api_key:
        raise RuntimeError("BITGN_API_KEY is required for start-run.")

    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_id, trial_map = _task_trial_map_for_run(
        benchmark_host=args.benchmark_host,
        benchmark_id=args.benchmark_id,
        task_ids=task_ids,
        api_key=api_key,
        batch_id=batch_id,
    )

    state = {
        "run_id": run_id,
        "benchmark_id": args.benchmark_id,
        "benchmark_host": args.benchmark_host,
        "run_name": LEADERBOARD_RUN_NAME,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "submitted_at": None,
        "status": "open",
        "task_ids": task_ids,
        "tasks": {
            task_id: {
                "trial_id": trial_map[task_id],
                "status": "pending",
                "last_batch_id": None,
                "last_started_at": None,
                "last_finished_at": None,
                "last_runner_exit": None,
                "last_outcome": None,
                "last_score": None,
                "last_details": [],
            }
            for task_id in task_ids
        },
    }
    _save_run_state(state)
    run_dir = _run_dir(run_id)
    _write_text(
        run_dir / "run_summary.txt",
        "\n".join(
            [
                f"Run ID: {run_id}",
                f"Benchmark ID: {args.benchmark_id}",
                f"Run Name: {LEADERBOARD_RUN_NAME}",
                f"Tasks: {', '.join(task_ids)}",
            ]
        ),
    )
    print(f"RUN_ID {run_id}")
    print(f"RUN_STATE {run_dir / 'run_state.json'}")
    return 0


def _tasks_to_run_from_state(state: dict, task_spec: str | None) -> tuple[list[str], list[str]]:
    if task_spec:
        requested = parse_task_spec(task_spec)
        missing = [task_id for task_id in requested if task_id not in state["tasks"]]
        if missing:
            raise ValueError(f"Tasks not present in run {state['run_id']}: {', '.join(missing)}")
        runnable = [task_id for task_id in requested if state["tasks"][task_id]["status"] != "completed"]
        skipped = [task_id for task_id in requested if state["tasks"][task_id]["status"] == "completed"]
        return runnable, skipped

    return ([
        task_id
        for task_id in state["task_ids"]
        if state["tasks"][task_id]["status"] != "completed"
    ], [])


def _run_tasks_command(args: argparse.Namespace) -> int:
    _print_command_started()
    state = _load_run_state(args.run_id)
    if state.get("submitted_at"):
        raise RuntimeError(f"Run {state['run_id']} is already submitted.")

    task_ids, skipped_task_ids = _tasks_to_run_from_state(state, args.task_id)
    if not task_ids:
        print(f"RUN_ID {state['run_id']}")
        print("TASKS none")
        if skipped_task_ids:
            print(f"SKIPPED_COMPLETED_TASKS {','.join(skipped_task_ids)}")
        return 0

    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    script_path = Path(__file__).resolve()
    trial_map = {task_id: state["tasks"][task_id]["trial_id"] for task_id in task_ids}
    print(f"RUN_ID {state['run_id']}")
    print(f"BATCH_ID {batch_id}")
    print(f"TASKS {','.join(task_ids)}")
    if skipped_task_ids:
        print(f"SKIPPED_COMPLETED_TASKS {','.join(skipped_task_ids)}")

    return _run_worker_pool(
        script_path=script_path,
        benchmark_id=state["benchmark_id"],
        benchmark_host=state["benchmark_host"],
        debug_preflight_deny=args.debug_preflight_deny,
        workers=args.workers,
        task_ids=task_ids,
        batch_id=batch_id,
        trial_map=trial_map,
        run_id=state["run_id"],
        run_state=state,
    )


def _end_run_command(args: argparse.Namespace) -> int:
    _print_command_started()
    state = _load_run_state(args.run_id)
    if state.get("submitted_at"):
        print(f"RUN_ID {state['run_id']}")
        print(f"SUBMITTED_AT {state['submitted_at']}")
        return 0
    finalized = _force_submit_unfinished_tasks(state)
    _submit_run(state["benchmark_host"], state["run_id"])
    state["submitted_at"] = datetime.now().isoformat(timespec="seconds")
    state["status"] = "submitted"
    _save_run_state(state)
    print(f"RUN_ID {state['run_id']}")
    if finalized:
        print(f"FORCE_SUBMITTED_TASKS {','.join(finalized)}")
    print(f"SUBMITTED_AT {state['submitted_at']}")
    return 0


def _status_command(args: argparse.Namespace) -> int:
    _print_command_started()
    state = _load_run_state(args.run_id)

    pending = [task_id for task_id in state["task_ids"] if state["tasks"][task_id]["status"] == "pending"]
    running = [task_id for task_id in state["task_ids"] if state["tasks"][task_id]["status"] == "running"]
    completed = [task_id for task_id in state["task_ids"] if state["tasks"][task_id]["status"] == "completed"]
    local_error = [task_id for task_id in state["task_ids"] if state["tasks"][task_id]["status"] == "local_error"]

    print(f"RUN_ID {state['run_id']}")
    print(f"BENCHMARK_ID {state['benchmark_id']}")
    print(f"RUN_STATUS {state.get('status', '(unknown)')}")
    print(f"SUBMITTED_AT {state.get('submitted_at') or '(not submitted)'}")
    print(f"TOTAL_TASKS {len(state['task_ids'])}")
    print(f"PENDING_COUNT {len(pending)}")
    print(f"RUNNING_COUNT {len(running)}")
    print(f"COMPLETED_COUNT {len(completed)}")
    print(f"LOCAL_ERROR_COUNT {len(local_error)}")
    print(f"PENDING_TASKS {','.join(pending) if pending else '(none)'}")
    print(f"RUNNING_TASKS {','.join(running) if running else '(none)'}")
    print(f"LOCAL_ERROR_TASKS {','.join(local_error) if local_error else '(none)'}")
    print(f"COMPLETED_TASKS {','.join(completed) if completed else '(none)'}")
    return 0


def _main_legacy(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.worker_mode:
        return _worker_main(args)
    return _parent_main(args)


def _main_lifecycle(argv: list[str]) -> int:
    parser = build_lifecycle_parser()
    args = parser.parse_args(argv)
    if args.command == "start-run":
        return _start_run_command(args)
    if args.command == "run-tasks":
        return _run_tasks_command(args)
    if args.command == "end-run":
        return _end_run_command(args)
    if args.command == "status":
        return _status_command(args)
    raise ValueError(f"Unsupported command: {args.command}")


def main() -> int:
    lifecycle_commands = {"start-run", "run-tasks", "end-run", "status"}
    argv = sys.argv[1:]
    if argv and argv[0] in lifecycle_commands:
        return _main_lifecycle(argv)
    return _main_legacy(argv)


if __name__ == "__main__":
    raise SystemExit(main())
