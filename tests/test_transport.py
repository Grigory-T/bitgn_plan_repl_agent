from __future__ import annotations

import os
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from pydantic import BaseModel

from plan_agent import utils
from plan_agent.progress import configure_progress


class ExampleResult(BaseModel):
    status: str


class TransportTests(unittest.TestCase):
    def tearDown(self) -> None:
        configure_progress(None, console=False)

    def _environment(self, **overrides: str) -> dict[str, str]:
        values = {
            "LLM_BASE_URL": "https://gateway.example/chat/completions",
            "LLM_API_KEY": "secret-for-test",
            "LLM_AUTH_HEADER": "X-Custom-Key",
            "LLM_AUTH_PREFIX": "<none>",
            "LLM_MODEL": "example-model",
            "LLM_CHOICES_PATH": "envelope.choices",
            "LLM_USAGE_PATH": "envelope.usage",
            "LLM_EXTRA_BODY_JSON": '{"model_option":{"enabled":false}}',
            "LLM_VERIFY_TLS": "false",
            "LLM_REQUEST_ATTEMPTS": "1",
            "LLM_SCHEMA_ATTEMPTS": "1",
        }
        values.update(overrides)
        return values

    def _response(self, content: str, finish_reason: str = "stop") -> Mock:
        response = Mock()
        response.status_code = 200
        response.headers = {}
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "envelope": {
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 4,
                    "total_tokens": 14,
                },
                "choices": [
                    {
                        "message": {"content": content},
                        "finish_reason": finish_reason,
                    }
                ]
            }
        }
        return response

    def test_configurable_request_and_wrapped_response(self) -> None:
        response = self._response("done")
        with (
            patch.dict(os.environ, self._environment(), clear=True),
            patch("plan_agent.utils.requests.post", return_value=response) as post,
        ):
            content, reasoning, finish_reason = utils._post_chat_completion(
                messages=[{"role": "user", "content": "hello"}],
                model="example-model",
                max_completion_tokens=24_000,
            )

        self.assertEqual(content, "done")
        self.assertEqual(reasoning, "")
        self.assertEqual(finish_reason, "stop")
        call = post.call_args
        self.assertEqual(call.args[0], "https://gateway.example/chat/completions")
        self.assertEqual(call.kwargs["headers"]["X-Custom-Key"], "secret-for-test")
        self.assertNotIn("Authorization", call.kwargs["headers"])
        self.assertFalse(call.kwargs["verify"])
        self.assertFalse(call.kwargs["json"]["stream"])
        self.assertEqual(call.kwargs["json"]["max_tokens"], 24_000)
        self.assertEqual(call.kwargs["json"]["model_option"], {"enabled": False})

    def test_structured_response_uses_schema_and_validates_json(self) -> None:
        response = self._response('{"status":"ok"}')
        with (
            patch.dict(os.environ, self._environment(), clear=True),
            patch("plan_agent.utils.requests.post", return_value=response) as post,
        ):
            result = utils.llm_structured(
                "return json", ExampleResult, model="example-model"
            )

        self.assertEqual(result.status, "ok")
        response_format = post.call_args.kwargs["json"]["response_format"]
        self.assertEqual(response_format["type"], "json_schema")

    def test_json_object_mode_uses_simpler_response_format(self) -> None:
        response = self._response('{"status":"ok"}')
        env = self._environment(LLM_STRUCTURED_OUTPUT="json_object")
        with (
            patch.dict(os.environ, env, clear=True),
            patch("plan_agent.utils.requests.post", return_value=response) as post,
        ):
            result = utils.llm_structured(
                "return json", ExampleResult, model="example-model"
            )

        self.assertEqual(result.status, "ok")
        response_format = post.call_args.kwargs["json"]["response_format"]
        self.assertEqual(response_format, {"type": "json_object"})

    def test_length_completion_is_rejected(self) -> None:
        response = self._response("partial", finish_reason="length")
        with (
            patch.dict(os.environ, self._environment(), clear=True),
            patch("plan_agent.utils.requests.post", return_value=response),
        ):
            with self.assertRaisesRegex(RuntimeError, "token limit"):
                utils._post_chat_completion(
                    messages=[{"role": "user", "content": "hello"}],
                    model="example-model",
                    max_completion_tokens=24_000,
                )

    def test_empty_completion_is_retried(self) -> None:
        empty = self._response("")
        success = self._response("done")
        env = self._environment(LLM_REQUEST_ATTEMPTS="2")
        with (
            patch.dict(os.environ, env, clear=True),
            patch(
                "plan_agent.utils.requests.post", side_effect=[empty, success]
            ) as post,
            patch("plan_agent.utils.time.sleep"),
        ):
            content, _, _ = utils._post_chat_completion(
                messages=[{"role": "user", "content": "hello"}],
                model="example-model",
                max_completion_tokens=24_000,
            )

        self.assertEqual(content, "done")
        self.assertEqual(post.call_count, 2)

    def test_text_content_blocks_are_supported(self) -> None:
        response = self._response("")
        response.json.return_value["envelope"]["choices"][0]["message"]["content"] = [
            {"type": "text", "text": "one"},
            {"type": "text", "text": " two"},
        ]
        with (
            patch.dict(os.environ, self._environment(), clear=True),
            patch("plan_agent.utils.requests.post", return_value=response),
        ):
            content, _, _ = utils._post_chat_completion(
                messages=[{"role": "user", "content": "hello"}],
                model="example-model",
                max_completion_tokens=24_000,
            )

        self.assertEqual(content, "one two")

    def test_protected_request_fields_cannot_be_overridden(self) -> None:
        env = self._environment(LLM_EXTRA_BODY_JSON='{"model":"other"}')
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(RuntimeError, "cannot override"):
                utils._extra_body()

    def test_authentication_can_be_omitted_for_a_local_endpoint(self) -> None:
        env = self._environment(LLM_AUTH_HEADER="<none>")
        del env["LLM_API_KEY"]
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(
                utils._auth_headers(), {"Content-Type": "application/json"}
            )

    def test_completion_limit_field_is_configurable(self) -> None:
        response = self._response("done")
        env = self._environment(LLM_MAX_TOKENS_FIELD="completion_limit")
        with (
            patch.dict(os.environ, env, clear=True),
            patch("plan_agent.utils.requests.post", return_value=response) as post,
        ):
            utils._post_chat_completion(
                messages=[{"role": "user", "content": "hello"}],
                model="example-model",
                max_completion_tokens=123,
            )

        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["completion_limit"], 123)
        self.assertNotIn("max_tokens", payload)

    def test_missing_endpoint_fails_before_network_call(self) -> None:
        env = self._environment()
        del env["LLM_BASE_URL"]
        with (
            patch.dict(os.environ, env, clear=True),
            patch("plan_agent.utils.requests.post") as post,
        ):
            with self.assertRaisesRegex(RuntimeError, "LLM_BASE_URL is required"):
                utils._post_chat_completion(
                    messages=[],
                    model="example-model",
                    max_completion_tokens=100,
                )
            post.assert_not_called()

    def test_pending_request_emits_neutral_heartbeat(self) -> None:
        response = self._response("done")

        def delayed_response(*args, **kwargs):
            time.sleep(1.1)
            return response

        env = self._environment(LLM_PROGRESS_INTERVAL_SECONDS="1")
        with TemporaryDirectory() as directory:
            log_path = Path(directory) / "run.log"
            configure_progress(log_path, console=False)
            with (
                patch.dict(os.environ, env, clear=True),
                patch(
                    "plan_agent.utils.requests.post",
                    side_effect=delayed_response,
                ),
            ):
                utils._post_chat_completion(
                    messages=[{"role": "user", "content": "private prompt"}],
                    model="private-model-name",
                    max_completion_tokens=24_000,
                    phase="Plan",
                )

            content = log_path.read_text(encoding="utf-8")
            self.assertIn("event=llm_request_waiting", content)
            self.assertIn("event=llm_completion_accepted", content)
            self.assertNotIn("private prompt", content)
            self.assertNotIn("private-model-name", content)
            self.assertNotIn("https://gateway.example", content)
            self.assertNotIn("secret-for-test", content)

    def test_standard_usage_is_written_to_neutral_log(self) -> None:
        response = self._response("done")
        with TemporaryDirectory() as directory:
            log_path = Path(directory) / "run.log"
            configure_progress(log_path, console=False)
            with (
                patch.dict(os.environ, self._environment(), clear=True),
                patch("plan_agent.utils.requests.post", return_value=response),
            ):
                utils._post_chat_completion(
                    messages=[{"role": "user", "content": "private prompt"}],
                    model="private-model-name",
                    max_completion_tokens=24_000,
                )

            content = log_path.read_text(encoding="utf-8")
            self.assertIn("prompt_tokens=10", content)
            self.assertIn("completion_tokens=4", content)
            self.assertIn("total_tokens=14", content)
            self.assertIn("output_tps_end_to_end=", content)
            self.assertIn("reasoning_chars=0", content)
            self.assertNotIn("private prompt", content)

    def test_missing_usage_does_not_reject_completion(self) -> None:
        response = self._response("done")
        del response.json.return_value["envelope"]["usage"]
        with (
            patch.dict(os.environ, self._environment(), clear=True),
            patch("plan_agent.utils.requests.post", return_value=response),
        ):
            content, _, _ = utils._post_chat_completion(
                messages=[{"role": "user", "content": "hello"}],
                model="example-model",
                max_completion_tokens=24_000,
            )

        self.assertEqual(content, "done")


if __name__ == "__main__":
    unittest.main()
