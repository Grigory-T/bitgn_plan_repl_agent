#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv


os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.dont_write_bytecode = True
load_dotenv()


DEFAULT_BENCHMARK_ID = os.getenv("BENCH_ID") or os.getenv("BENCHMARK_ID") or "bitgn/ecom1-dev"
DEFAULT_BENCHMARK_HOST = os.getenv("BITGN_HOST") or os.getenv("BENCHMARK_HOST") or "https://api.bitgn.com"
DEFAULT_RUN_NAME = os.getenv("BITGN_RUN_NAME") or "plan_repl_agent ecom"


def _task_num(raw: str) -> tuple[int, int]:
    value = raw.strip().lower()
    match = re.fullmatch(r"t?(\d+)", value)
    if not match:
        raise ValueError(f"Invalid task id: {raw}")
    digits = match.group(1)
    return int(digits), len(digits)


def _task_id(num: int, width: int = 2) -> str:
    return f"t{num:0{width}d}"


def parse_task_spec(task_spec: str) -> list[str]:
    task_ids: list[str] = []
    seen: set[str] = set()
    for part in [item.strip() for item in task_spec.split(",") if item.strip()]:
        if "-" in part:
            left, right = [item.strip() for item in part.split("-", 1)]
            start, start_width = _task_num(left)
            end, end_width = _task_num(right)
            if start > end:
                raise ValueError(f"Invalid task range: {part}")
            width = max(start_width, end_width, 2)
            expanded = [_task_id(num, width) for num in range(start, end + 1)]
        else:
            num, width = _task_num(part)
            expanded = [_task_id(num, max(width, 2))]

        for task_id in expanded:
            if task_id not in seen:
                seen.add(task_id)
                task_ids.append(task_id)
    if not task_ids:
        raise ValueError("No task ids parsed.")
    return task_ids


def _proto_text(value, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _safe_score(response) -> float | None:
    try:
        if getattr(response, "score_available", False):
            return float(response.score)
    except Exception:
        pass
    try:
        if hasattr(response, "HasField") and response.HasField("score"):
            return float(response.score)
    except Exception:
        pass
    return None


def _score_text(score: float | None) -> str:
    return "none" if score is None else f"{score:.2f}"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _run_log_dir(batch_id: str, task_id: str) -> Path:
    from plan_agent.log import _init_log_dir

    return _init_log_dir(task_id=task_id, batch_id=batch_id)


def _run_one_trial(
    *,
    benchmark_host: str,
    benchmark_id: str,
    batch_id: str,
    task_id: str | None = None,
    trial_id: str | None = None,
) -> dict:
    from bitgn.harness_connect import HarnessServiceClientSync
    from bitgn.harness_pb2 import EndTrialRequest, StartPlaygroundRequest, StartTrialRequest
    from plan_agent.executor import initialize_runtime_globals, reset_persistent_globals
    from plan_agent.response import decide_response
    from plan_agent.run_agent import run_agent
    import ecom_runtime

    client = HarnessServiceClientSync(benchmark_host)
    started_at = datetime.now().isoformat(timespec="seconds")
    started = time.monotonic()
    trial = None
    effective_task_id = task_id or "trial"
    task_text = task_id or ""
    harness_url = ""
    final_message = ""
    final_outcome = "OUTCOME_ERR_INTERNAL"
    final_refs: list[str] = []
    score = None
    score_detail: list[str] = []
    runner_exit = 0

    try:
        if trial_id:
            trial = client.start_trial(StartTrialRequest(trial_id=trial_id))
        else:
            if not task_id:
                raise ValueError("task_id is required for playground trials")
            trial = client.start_playground(
                StartPlaygroundRequest(benchmark_id=benchmark_id, task_id=task_id)
            )

        effective_task_id = _proto_text(getattr(trial, "task_id", None), effective_task_id)
        effective_trial_id = _proto_text(getattr(trial, "trial_id", None), trial_id or "")
        task_text = _proto_text(getattr(trial, "instruction", None), effective_task_id)
        harness_url = _proto_text(getattr(trial, "harness_url", None))
        if not harness_url:
            raise RuntimeError("BitGN did not return a harness_url.")

        os.environ["BITGN_HARNESS_URL"] = harness_url
        reset_persistent_globals()
        initialize_runtime_globals()
        ecom_runtime.reset()
        ecom_runtime.configure(harness_url)

        agent_result, log_dir, step_results = run_agent(
            task_text,
            task_id=effective_task_id,
            batch_id=batch_id,
        )
        response = decide_response(
            task=task_text,
            agent_answer=agent_result,
            step_results=step_results,
            log_dir=log_dir,
        )
        final_message = response.message
        final_outcome = response.outcome
        final_refs = response.refs
        if response.should_submit_to_bitgn:
            ecom_runtime.answer(final_message, final_outcome, final_refs)

    except Exception as exc:
        runner_exit = 1
        final_message = f"Internal runner error: {exc}"
        final_outcome = "OUTCOME_ERR_INTERNAL"
        final_refs = []
        if harness_url:
            try:
                ecom_runtime.reset()
                ecom_runtime.configure(harness_url)
                ecom_runtime.answer(final_message, final_outcome, final_refs)
            except Exception:
                pass
        log_dir = str(_run_log_dir(batch_id, effective_task_id))
        Path(log_dir, "runner_exception.txt").write_text(traceback.format_exc(), encoding="utf-8")

    if trial is not None:
        try:
            effective_trial_id = _proto_text(getattr(trial, "trial_id", None), trial_id or "")
            result = client.end_trial(EndTrialRequest(trial_id=effective_trial_id))
            score = _safe_score(result)
            score_detail = [str(item) for item in getattr(result, "score_detail", [])]
        except Exception as exc:
            runner_exit = 1
            score_detail = [f"end_trial failed: {exc}"]

    elapsed = time.monotonic() - started
    payload = {
        "task_id": effective_task_id,
        "trial_id": _proto_text(getattr(trial, "trial_id", None)) if trial is not None else trial_id,
        "benchmark_id": benchmark_id,
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "elapsed_seconds": elapsed,
        "runner_exit": runner_exit,
        "message": final_message,
        "outcome": final_outcome,
        "refs": final_refs,
        "score": score,
        "score_detail": score_detail,
    }
    _write_json(_run_log_dir(batch_id, effective_task_id) / "runner_result.json", payload)
    print(
        f"{effective_task_id}: exit={runner_exit} outcome={final_outcome} "
        f"score={_score_text(score)} elapsed={elapsed:.1f}s",
        flush=True,
    )
    if score_detail:
        for line in score_detail:
            print(f"  {line}", flush=True)
    return payload


def _available_task_ids(client, benchmark_id: str) -> list[str]:
    from bitgn.harness_pb2 import GetBenchmarkRequest

    benchmark = client.get_benchmark(GetBenchmarkRequest(benchmark_id=benchmark_id))
    return [str(task.task_id) for task in benchmark.tasks]


def _run_selected_tasks(args: argparse.Namespace, task_ids: list[str]) -> int:
    from bitgn.harness_connect import HarnessServiceClientSync
    from bitgn.harness_pb2 import GetRunRequest, StartRunRequest, SubmitRunRequest

    api_key = (os.getenv("BITGN_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("BITGN_API_KEY is required because ECOM DEV does not expose StartPlayground.")

    client = HarnessServiceClientSync(args.benchmark_host)
    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run = client.start_run(
        StartRunRequest(
            benchmark_id=args.benchmark_id,
            name=args.run_name + " selected",
            api_key=api_key,
        )
    )
    run_id = _proto_text(run.run_id)
    run_info = client.get_run(GetRunRequest(run_id=run_id))
    trial_map = {str(head.task_id): str(head.trial_id) for head in run_info.trials}
    missing = [task_id for task_id in task_ids if task_id not in trial_map]
    if missing:
        raise ValueError(f"Run did not contain requested tasks: {', '.join(missing)}")

    print("MODE selected-run", flush=True)
    print(f"RUN_ID {run_id}", flush=True)
    print(f"BATCH_ID {batch_id}", flush=True)
    print("NOTE selected-task runs are not submitted unless --submit-selected is set", flush=True)
    results = [
        _run_one_trial(
            benchmark_host=args.benchmark_host,
            benchmark_id=args.benchmark_id,
            batch_id=batch_id,
            trial_id=trial_map[task_id],
        )
        for task_id in task_ids
    ]
    if args.submit_selected:
        submit = client.submit_run(SubmitRunRequest(run_id=run_id, force=True))
        print(f"SUBMITTED_RUN {submit.run_id}", flush=True)
    _print_summary(results)
    return max(int(item["runner_exit"]) for item in results) if results else 0


def _run_leaderboard(args: argparse.Namespace) -> int:
    from bitgn.harness_connect import HarnessServiceClientSync
    from bitgn.harness_pb2 import GetRunRequest, StartRunRequest, SubmitRunRequest

    api_key = (os.getenv("BITGN_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("BITGN_API_KEY is required for a full benchmark run.")

    client = HarnessServiceClientSync(args.benchmark_host)
    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run = client.start_run(
        StartRunRequest(
            benchmark_id=args.benchmark_id,
            name=args.run_name,
            api_key=api_key,
        )
    )
    run_id = _proto_text(run.run_id)
    print(f"MODE leaderboard", flush=True)
    print(f"RUN_ID {run_id}", flush=True)
    print(f"BATCH_ID {batch_id}", flush=True)

    run_info = client.get_run(GetRunRequest(run_id=run_id))
    heads = sorted(list(run_info.trials), key=lambda item: item.num)
    trial_ids = [head.trial_id for head in heads] or list(run.trial_ids)
    results = [
        _run_one_trial(
            benchmark_host=args.benchmark_host,
            benchmark_id=args.benchmark_id,
            batch_id=batch_id,
            trial_id=trial_id,
        )
        for trial_id in trial_ids
    ]

    submit = client.submit_run(SubmitRunRequest(run_id=run_id, force=True))
    print(f"SUBMITTED_RUN {submit.run_id}", flush=True)
    _print_summary(results)
    return max(int(item["runner_exit"]) for item in results) if results else 0


def _print_summary(results: list[dict]) -> None:
    scored = [item for item in results if item.get("score") is not None]
    if scored:
        total = sum(float(item["score"]) for item in scored)
        print(f"SUMMARY {total:.2f}/{len(scored)} scored trials", flush=True)
    else:
        print("SUMMARY no scores available", flush=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the plan/repl ECOM agent on BitGN.")
    parser.add_argument("--task-id", help="Playground task spec, e.g. t01, t01,t04, or t01-t05.")
    parser.add_argument("--benchmark-id", default=DEFAULT_BENCHMARK_ID)
    parser.add_argument("--benchmark-host", default=DEFAULT_BENCHMARK_HOST)
    parser.add_argument("--run-name", default=DEFAULT_RUN_NAME)
    parser.add_argument("--list-tasks", action="store_true", help="List benchmark task ids and exit.")
    parser.add_argument(
        "--submit-selected",
        action="store_true",
        help="Submit a selected-task run. By default selected runs are left unsubmitted.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    from bitgn.harness_connect import HarnessServiceClientSync

    client = HarnessServiceClientSync(args.benchmark_host)
    if args.list_tasks:
        print("\n".join(_available_task_ids(client, args.benchmark_id)))
        return 0

    if args.task_id:
        task_ids = parse_task_spec(args.task_id)
        available = set(_available_task_ids(client, args.benchmark_id))
        missing = [task_id for task_id in task_ids if task_id not in available]
        if missing:
            raise ValueError(f"Tasks not present in {args.benchmark_id}: {', '.join(missing)}")
        return _run_selected_tasks(args, task_ids)

    return _run_leaderboard(args)


if __name__ == "__main__":
    raise SystemExit(main())
