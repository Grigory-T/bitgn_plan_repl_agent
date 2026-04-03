#!/usr/bin/env python3

import os
import sys
import shutil
import uuid
from pathlib import Path
import argparse
import re


os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.dont_write_bytecode = True


def _print_section(title: str) -> None:
    print(f"\n[{title}]", flush=True)


def _short_text(value: str, limit: int = 240) -> str:
    text = " ".join((value or "").strip().split())
    if len(text) <= limit:
        return text
    return text[:limit - 3].rstrip() + "..."


def _score_text(score: float | None) -> str:
    return "none" if score is None else f"{score:.2f}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one or more BitGN sandbox tasks end-to-end.")
    parser.add_argument(
        "--task-id",
        required=True,
        help="Task spec: one task (`t04` or `4`), comma list (`t01,t03,8`), or inclusive range (`1-5` or `t01-t05`)",
    )
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

    client = HarnessServiceClientSync(args.benchmark_host)
    task_ids = parse_task_spec(args.task_id)

    if not args.no_clean:
        clear_directories(project)

    batch_results: list[tuple[str, float | None, int, list[str]]] = []
    worst_returncode = 0

    for index, task_id in enumerate(task_ids, start=1):
        trial = client.start_playground(
            StartPlaygroundRequest(
                benchmark_id=args.benchmark_id,
                task_id=task_id,
            )
        )

        print("", flush=True)
        print("=" * 72, flush=True)
        if len(task_ids) > 1:
            print(f"BATCH {index}/{len(task_ids)}", flush=True)
        print(f"TASK {task_id}", flush=True)
        print(f"TRIAL_ID {trial.trial_id}", flush=True)
        _print_section("Instruction")
        print(trial.instruction)
        _print_section("Runtime")
        print(f"HARNESS_URL {trial.harness_url}", flush=True)

        before = {p.name for p in (project / "logs").iterdir() if p.is_dir()} if (project / "logs").exists() else set()

        os.environ["BITGN_HARNESS_URL"] = trial.harness_url
        os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

        reset_persistent_globals()
        initialize_runtime_globals()
        bitgn_runtime.reset()
        bitgn_runtime.configure(trial.harness_url)

        run_dir = create_run_dir(project)
        original_cwd = Path.cwd()
        log_dir = None
        proc_returncode = 0

        print(f"RUN_DIR {run_dir}", flush=True)

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

        _print_section("Result")
        print(f"AGENT { _short_text(agent_result) }", flush=True)
        print(f"ANSWER { _short_text(response.message) }", flush=True)
        if response.refs:
            print("REFS", flush=True)
            for ref in response.refs:
                print(f"- {ref}", flush=True)
        else:
            print("REFS (none)", flush=True)

        print(f"RUNNER_EXIT {proc_returncode}", flush=True)

        after = {p.name for p in (project / "logs").iterdir() if p.is_dir()} if (project / "logs").exists() else set()
        new_logs = sorted(after - before)

        result = client.end_trial(EndTrialRequest(trial_id=trial.trial_id))
        score = result.score if result.HasField("score") else None
        _print_section("Evaluation")
        print(f"SCORE {_score_text(score)}", flush=True)
        if result.score_detail:
            for item in result.score_detail:
                print(f"- {item}", flush=True)
        else:
            print("- (none)", flush=True)

        _print_section("Logs")
        for new_log_dir in new_logs:
            log_path = project / "logs" / new_log_dir
            print(str(log_path), flush=True)
            record_bitgn_evaluation(
                log_path,
                trial_id=trial.trial_id,
                score=str(score),
                details=list(result.score_detail),
            )

        batch_results.append((task_id, score, proc_returncode, list(result.score_detail)))
        worst_returncode = max(worst_returncode, proc_returncode)

    if len(batch_results) > 1:
        print("", flush=True)
        print("=" * 72, flush=True)
        _print_section("Batch Stats")
        passed = 0
        scored = 0
        total = 0.0
        for task_id, score, returncode, details in batch_results:
            if score is not None:
                scored += 1
                total += score
                if score == 1.0:
                    passed += 1
            status = "ok" if returncode == 0 else f"rc={returncode}"
            score_text = _score_text(score)
            detail_text = details[0] if details else "-"
            print(f"{task_id} score={score_text} {status} {detail_text}")
        avg_text = "none" if not scored else f"{(total / scored):.2f}"
        print(f"TOTAL pass={passed}/{len(batch_results)} avg={avg_text}")

    return 0 if worst_returncode == 0 else worst_returncode


if __name__ == "__main__":
    raise SystemExit(main())
