from __future__ import annotations

import ast
import json
import os
import time
import warnings
from typing import Any, Literal

import requests
from dotenv import load_dotenv
from pydantic import BaseModel
from urllib3.exceptions import InsecureRequestWarning

from .json_schemas import get_schema_dict

load_dotenv()

DEFAULT_MAX_COMPLETION_TOKENS = 24_000
DEFAULT_REQUEST_TIMEOUT_SECONDS = 300
DEFAULT_REQUEST_ATTEMPTS = 3


def _env_int(name: str, default: int, *, minimum: int = 1) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer, got {raw!r}.") from exc
    if value < minimum:
        raise RuntimeError(f"{name} must be at least {minimum}, got {value}.")
    return value


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{name} must be true or false, got {raw!r}.")


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required.")
    return value


def _default_model() -> str:
    return os.getenv("LLM_MODEL", "").strip()


# These names remain public because the planning modules import them. Values are
# provider-neutral: callers choose concrete model identifiers through the
# environment, and runtime validation gives a clear error if none was supplied.
LLM_MODEL_PLAN = os.getenv("LLM_MODEL_PLAN", _default_model()).strip()
LLM_MODEL_DECISION = os.getenv("LLM_MODEL_DECISION", LLM_MODEL_PLAN).strip()
LLM_MODEL_REPLAN = os.getenv("LLM_MODEL_REPLAN", LLM_MODEL_PLAN).strip()
LLM_MODEL_RESPONSE = os.getenv("LLM_MODEL_RESPONSE", LLM_MODEL_PLAN).strip()
LLM_MODEL_AGENT = os.getenv("LLM_MODEL_AGENT", _default_model()).strip()


def _model_or_error(model: str | None, fallback: str) -> str:
    selected = (model or fallback).strip()
    if not selected:
        raise RuntimeError(
            "No LLM model is configured. Set LLM_MODEL, or set both "
            "LLM_MODEL_PLAN and LLM_MODEL_AGENT."
        )
    return selected


def _auth_headers() -> dict[str, str]:
    header_name = os.getenv("LLM_AUTH_HEADER", "Authorization").strip()
    if header_name.casefold() in {"none", "<none>"}:
        return {"Content-Type": "application/json"}
    if not header_name or any(char in header_name for char in "\r\n:"):
        raise RuntimeError("LLM_AUTH_HEADER is not a valid HTTP header name.")

    api_key = _required_env("LLM_API_KEY")
    prefix = os.getenv("LLM_AUTH_PREFIX", "Bearer").strip()
    if prefix.casefold() in {"none", "<none>"}:
        prefix = ""
    value = f"{prefix} {api_key}" if prefix else api_key
    return {
        "Content-Type": "application/json",
        header_name: value,
    }


def _extra_body() -> dict[str, Any]:
    raw = os.getenv("LLM_EXTRA_BODY_JSON", "{}").strip() or "{}"
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"LLM_EXTRA_BODY_JSON is invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError("LLM_EXTRA_BODY_JSON must contain a JSON object.")

    protected = {"model", "messages", "stream", "response_format"}
    overlap = protected.intersection(value)
    if overlap:
        names = ", ".join(sorted(overlap))
        raise RuntimeError(
            f"LLM_EXTRA_BODY_JSON cannot override agent-controlled fields: {names}."
        )
    return value


def _value_at_path(value: Any, path: str) -> Any:
    current = value
    for segment in path.split("."):
        segment = segment.strip()
        if not segment:
            raise ValueError("response path contains an empty segment")
        if isinstance(current, list):
            try:
                current = current[int(segment)]
            except (ValueError, IndexError) as exc:
                raise ValueError(f"cannot select list item {segment!r}") from exc
        elif isinstance(current, dict):
            if segment not in current:
                raise ValueError(f"response path segment {segment!r} is missing")
            current = current[segment]
        else:
            raise ValueError(f"cannot select {segment!r} from {type(current).__name__}")
    return current


def _retry_delay_seconds(response: requests.Response, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return min(60.0, max(0.0, float(retry_after)))
        except ValueError:
            pass
    return min(60.0, float(2**attempt))


def _post_chat_completion(
    *,
    messages: list[dict[str, Any]],
    model: str,
    max_completion_tokens: int,
    response_format: dict[str, Any] | None = None,
) -> tuple[str, str, str | None]:
    endpoint = _required_env("LLM_BASE_URL")
    max_tokens_field = os.getenv("LLM_MAX_TOKENS_FIELD", "max_tokens").strip()
    if not max_tokens_field or any(char in max_tokens_field for char in "\r\n."):
        raise RuntimeError("LLM_MAX_TOKENS_FIELD is not a valid JSON field name.")
    if max_tokens_field in {"model", "messages", "stream", "response_format"}:
        raise RuntimeError(
            "LLM_MAX_TOKENS_FIELD conflicts with an agent-controlled field."
        )

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": 0,
        "stream": False,
        max_tokens_field: max_completion_tokens,
    }
    payload.update(_extra_body())
    if response_format is not None:
        payload["response_format"] = response_format

    verify_tls = _env_bool("LLM_VERIFY_TLS", True)
    timeout = _env_int("LLM_REQUEST_TIMEOUT_SECONDS", DEFAULT_REQUEST_TIMEOUT_SECONDS)
    attempts = _env_int("LLM_REQUEST_ATTEMPTS", DEFAULT_REQUEST_ATTEMPTS)
    response: requests.Response | None = None

    for attempt in range(attempts):
        try:
            with warnings.catch_warnings():
                if not verify_tls:
                    warnings.simplefilter("ignore", InsecureRequestWarning)
                response = requests.post(
                    endpoint,
                    headers=_auth_headers(),
                    json=payload,
                    verify=verify_tls,
                    timeout=timeout,
                )
        except requests.RequestException as exc:
            if attempt + 1 == attempts:
                raise RuntimeError(
                    f"LLM HTTP request failed after {attempts} attempt(s): {exc}"
                ) from exc
            time.sleep(min(60.0, float(2**attempt)))
            continue

        if response.status_code == 429 or 500 <= response.status_code <= 599:
            if attempt + 1 < attempts:
                time.sleep(_retry_delay_seconds(response, attempt))
                continue

        try:
            response.raise_for_status()
        except requests.RequestException as exc:
            request_id = response.headers.get("x-request-id") or response.headers.get(
                "request-id"
            )
            detail = f"; request_id={request_id}" if request_id else ""
            response_detail = response.text.strip()[:2_000]
            if response_detail:
                detail += f"; response={response_detail}"
            raise RuntimeError(
                f"LLM HTTP request failed with status {response.status_code}{detail}."
            ) from exc
        break

    if response is None:  # Defensive; the loop always returns or assigns it.
        raise RuntimeError("LLM HTTP request did not produce a response.")

    try:
        body = response.json()
        choices_path = os.getenv("LLM_CHOICES_PATH", "choices").strip()
        choices = _value_at_path(body, choices_path)
        choice = choices[0]
        message = choice["message"]
        content = message.get("content") or ""
        finish_reason = choice.get("finish_reason")
        if finish_reason == "length":
            raise ValueError("completion reached its token limit")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("completion content is empty")
        reasoning = message.get("reasoning_content") or message.get("reasoning") or ""
        if not isinstance(reasoning, str):
            reasoning = ""
        return content, reasoning.strip(), finish_reason
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise RuntimeError(f"Invalid LLM response contract: {exc}") from exc


def _structured_output_mode() -> str:
    mode = os.getenv("LLM_STRUCTURED_OUTPUT", "json_schema").strip().casefold()
    if mode not in {"json_schema", "prompt_only"}:
        raise RuntimeError(
            "LLM_STRUCTURED_OUTPUT must be 'json_schema' or 'prompt_only'."
        )
    return mode


def llm_structured(
    prompt: str,
    response_model: type[BaseModel],
    model: str | None = None,
) -> BaseModel:
    schema = (
        get_schema_dict(response_model.__name__) or response_model.model_json_schema()
    )
    response_format = None
    if _structured_output_mode() == "json_schema":
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "response_schema",
                "description": response_model.__name__,
                "strict": False,
                "schema": schema,
            },
        }

    selected_model = _model_or_error(model, LLM_MODEL_PLAN)
    max_tokens = _env_int("LLM_MAX_COMPLETION_TOKENS", DEFAULT_MAX_COMPLETION_TOKENS)
    validation_attempts = _env_int("LLM_SCHEMA_ATTEMPTS", 3)
    messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
    errors: list[str] = []

    for attempt in range(validation_attempts):
        content, _, finish_reason = _post_chat_completion(
            messages=messages,
            model=selected_model,
            max_completion_tokens=max_tokens,
            response_format=response_format,
        )
        try:
            return _validate_structured_response(content, response_model)
        except Exception as exc:
            errors.append(str(exc))
            if attempt + 1 == validation_attempts:
                suffix = f"; finish_reason={finish_reason}" if finish_reason else ""
                joined = " | ".join(errors)
                raise RuntimeError(
                    f"Invalid structured LLM response after "
                    f"{validation_attempts} attempt(s){suffix}: {joined}"
                ) from exc
            messages.extend(
                [
                    {"role": "assistant", "content": content},
                    {
                        "role": "user",
                        "content": (
                            "The previous response did not validate against the required "
                            f"JSON schema ({exc}). Return one corrected JSON object only."
                        ),
                    },
                ]
            )

    raise RuntimeError("Structured response validation ended unexpectedly.")


def _validate_structured_response(
    content: str, response_model: type[BaseModel]
) -> BaseModel:
    try:
        return response_model.model_validate_json(content)
    except Exception:
        cleaned = _extract_json_object(content)
        return response_model.model_validate_json(cleaned)


def _extract_json_object(content: str) -> str:
    text = (content or "").strip()
    if not text:
        raise ValueError("Structured response is empty.")

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(
            f"Structured response does not contain a JSON object: {text[:200]!r}"
        )

    candidate = text[start : end + 1]
    json.loads(candidate)
    return candidate


def llm(
    messages: list[dict[str, Any]], model: str | None = None
) -> tuple[str, list, str]:
    content, reasoning, _ = _post_chat_completion(
        messages=messages,
        model=_model_or_error(model, LLM_MODEL_AGENT),
        max_completion_tokens=_env_int(
            "LLM_MAX_COMPLETION_TOKENS", DEFAULT_MAX_COMPLETION_TOKENS
        ),
    )

    class ResponseBlock(BaseModel):
        block_id: int
        block_type: Literal["python", "text"]
        block_text: str

    blocks: list[ResponseBlock] = []

    idx = 0
    block_idx = 0
    open_tag = "<python>"
    close_tag = "</python>"
    while True:
        start = content.find(open_tag, idx)
        if start == -1:
            tail = content[idx:]
            if tail:
                blocks.append(
                    ResponseBlock(
                        block_id=block_idx,
                        block_type="text",
                        block_text=tail,
                    )
                )
            break

        if start > idx:
            blocks.append(
                ResponseBlock(
                    block_id=block_idx,
                    block_type="text",
                    block_text=content[idx:start],
                )
            )
            block_idx += 1

        code_start = start + len(open_tag)
        close = content.find(close_tag, code_start)
        if close == -1:
            code_part = content[code_start:]
            idx = len(content)
        else:
            code_part = content[code_start:close]
            idx = close + len(close_tag)

        blocks.append(
            ResponseBlock(
                block_id=block_idx,
                block_type="python",
                block_text=code_part,
            )
        )
        block_idx += 1

    return content, blocks, reasoning.strip()


def check_assigned_variables(code: str) -> bool:
    """Check if final_answer or step_status is assigned in the code string."""
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in (
                        "final_answer",
                        "step_status",
                    ):
                        return True
                    if isinstance(target, (ast.Tuple, ast.List)):
                        for elt in target.elts:
                            if isinstance(elt, ast.Name) and elt.id in (
                                "final_answer",
                                "step_status",
                            ):
                                return True
        return False
    except Exception:
        return False


def format_step_variables(variables: list) -> str:
    """Format list of StepVariable objects into readable string."""
    if not variables:
        return "None"

    lines = []
    for var in variables:
        lines.append(
            f"  - {var.variable_name} ({var.variable_data_type}): "
            f"{var.variable_description}"
        )

    return "\n" + "\n".join(lines)
