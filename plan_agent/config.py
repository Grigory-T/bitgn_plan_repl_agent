from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values

CONFIG_KEYS = {
    "LLM_API_KEY",
    "LLM_AUTH_HEADER",
    "LLM_AUTH_PREFIX",
    "LLM_BASE_URL",
    "LLM_CHOICES_PATH",
    "LLM_EXTRA_BODY_JSON",
    "LLM_MAX_COMPLETION_TOKENS",
    "LLM_MAX_TOKENS_FIELD",
    "LLM_MODEL",
    "LLM_MODEL_AGENT",
    "LLM_MODEL_DECISION",
    "LLM_MODEL_PLAN",
    "LLM_MODEL_REPLAN",
    "LLM_MODEL_RESPONSE",
    "LLM_REQUEST_ATTEMPTS",
    "LLM_REQUEST_TIMEOUT_SECONDS",
    "LLM_SCHEMA_ATTEMPTS",
    "LLM_STRUCTURED_OUTPUT",
    "LLM_VERIFY_TLS",
}


def default_config_path() -> Path:
    return Path(__file__).resolve().parent.parent / "llm_config.txt"


def load_runtime_config(path: str | Path) -> Path:
    config_path = Path(path).expanduser().resolve()
    if not config_path.is_file():
        raise RuntimeError(
            f"Configuration file not found: {config_path}. "
            "Copy llm_config.example.txt to llm_config.txt and edit it."
        )

    values = dotenv_values(
        config_path,
        encoding="utf-8-sig",
        interpolate=False,
    )
    unknown = sorted(key for key in values if key not in CONFIG_KEYS)
    if unknown:
        raise RuntimeError("Unknown configuration setting(s): " + ", ".join(unknown))

    # The selected file is authoritative. This prevents stale values inherited
    # from a shell or parent process from changing the requested provider/model.
    for key in tuple(os.environ):
        if key.startswith("LLM_"):
            os.environ.pop(key, None)

    for key, value in values.items():
        if value is not None:
            os.environ[key] = value

    required = ("LLM_BASE_URL", "LLM_MODEL")
    missing = [key for key in required if not os.environ.get(key, "").strip()]
    if missing:
        raise RuntimeError(
            "Missing required configuration setting(s): " + ", ".join(missing)
        )

    placeholders = ("your-", "example.", "replace-me", "paste-")
    for key in ("LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY"):
        value = os.environ.get(key, "").strip().casefold()
        if value and any(marker in value for marker in placeholders):
            raise RuntimeError(f"Replace the placeholder value for {key}.")

    return config_path
