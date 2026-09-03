from __future__ import annotations

import re
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

_LOG_PATH: Path | None = None
_CONSOLE = False
_STARTED_AT = time.monotonic()
_LOCK = threading.Lock()
_ALLOWED_FIELDS = {
    "action",
    "after_step",
    "attempt",
    "attempts",
    "block_count",
    "block_number",
    "call_id",
    "code_chars",
    "completed_steps",
    "completion_limit",
    "completion_tokens",
    "delay_seconds",
    "error_type",
    "finish_reason",
    "input_count",
    "message_count",
    "output_count",
    "output_tps_end_to_end",
    "phase",
    "planned_steps",
    "process_id",
    "prompt_tokens",
    "remaining_steps",
    "reason",
    "request_elapsed_seconds",
    "response_chars",
    "reasoning_chars",
    "result_chars",
    "schema_attempt",
    "status_code",
    "stderr_chars",
    "stdout_chars",
    "step_number",
    "success",
    "timeout_seconds",
    "total_tokens",
    "turn_number",
    "warning_count",
}


def configure_progress(path: Path | None, *, console: bool = True) -> None:
    """Configure neutral progress reporting for one process-local run."""
    global _CONSOLE, _LOG_PATH, _STARTED_AT

    with _LOCK:
        _LOG_PATH = Path(path) if path is not None else None
        _CONSOLE = console
        _STARTED_AT = time.monotonic()
        if _LOG_PATH is not None:
            _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            _LOG_PATH.write_text("", encoding="utf-8")


def _safe_token(value: Any) -> str:
    if value is None:
        return "none"
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float):
        return f"{value:.3f}"
    if isinstance(value, int):
        return str(value)

    # Event fields are deliberately short machine-state labels, never prompts,
    # paths, model responses, endpoints, credentials, or workbook contents.
    text = re.sub(r"[^A-Za-z0-9_.:/-]+", "_", str(value).strip())
    return (text.strip("_") or "empty")[:80]


def progress_event(event: str, **fields: Any) -> None:
    """Append and print one content-free progress event when configured."""
    with _LOCK:
        if _LOG_PATH is None and not _CONSOLE:
            return

        unexpected = sorted(set(fields).difference(_ALLOWED_FIELDS))
        if unexpected:
            raise ValueError(
                "Neutral progress event contains unapproved field(s): "
                + ", ".join(unexpected)
            )

        timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
        elapsed = time.monotonic() - _STARTED_AT
        parts = [
            timestamp,
            f"elapsed_seconds={elapsed:.3f}",
            f"event={_safe_token(event)}",
        ]
        parts.extend(
            f"{_safe_token(key)}={_safe_token(value)}"
            for key, value in sorted(fields.items())
        )
        line = " ".join(parts)

        if _LOG_PATH is not None:
            with _LOG_PATH.open("a", encoding="utf-8") as log_file:
                log_file.write(line + "\n")
                log_file.flush()
        if _CONSOLE:
            print(f"[agent] {line}", flush=True)
