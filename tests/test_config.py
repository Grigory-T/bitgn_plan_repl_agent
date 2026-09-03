from __future__ import annotations

import os
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from llm_preflight import main as preflight_main
from plan_agent.config import load_runtime_config


class ConfigTests(unittest.TestCase):
    def _write(self, directory: str, text: str) -> Path:
        path = Path(directory) / "settings.txt"
        path.write_text(text, encoding="utf-8-sig")
        return path

    def test_file_is_authoritative_and_clears_stale_llm_values(self) -> None:
        with TemporaryDirectory() as directory:
            path = self._write(
                directory,
                "\n".join(
                    [
                        "LLM_BASE_URL=http://127.0.0.1:8000/v1/chat/completions",
                        "LLM_MODEL=local-model",
                        "LLM_AUTH_HEADER=<none>",
                        "LLM_API_KEY=",
                    ]
                ),
            )
            initial = {
                "LLM_MODEL_PLAN": "stale-model",
                "LLM_UNUSED_OLD_SETTING": "stale",
                "UNRELATED_SETTING": "preserved",
            }
            with patch.dict(os.environ, initial, clear=True):
                loaded = load_runtime_config(path)
                self.assertEqual(loaded, path.resolve())
                self.assertEqual(os.environ["LLM_MODEL"], "local-model")
                self.assertNotIn("LLM_MODEL_PLAN", os.environ)
                self.assertNotIn("LLM_UNUSED_OLD_SETTING", os.environ)
                self.assertEqual(os.environ["UNRELATED_SETTING"], "preserved")

    def test_unknown_setting_is_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            path = self._write(
                directory,
                "LLM_BASE_URL=http://localhost/v1/chat/completions\n"
                "LLM_MODEL=model\n"
                "LLM_MODELL=typo\n",
            )
            with self.assertRaisesRegex(RuntimeError, "LLM_MODELL"):
                load_runtime_config(path)

    def test_placeholder_is_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            path = self._write(
                directory,
                "LLM_BASE_URL=https://your-gateway.example/v1/chat/completions\n"
                "LLM_MODEL=your-model-id\n",
            )
            with self.assertRaisesRegex(RuntimeError, "placeholder"):
                load_runtime_config(path)

    def test_missing_file_has_setup_instruction(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "missing.txt"
            with self.assertRaisesRegex(RuntimeError, "llm_config.example.txt"):
                load_runtime_config(path)

    def test_preflight_reports_config_error_without_starting_model_code(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "missing.txt"
            stderr = StringIO()
            with redirect_stderr(stderr):
                exit_code = preflight_main(["--config", str(path)])
            self.assertEqual(exit_code, 2)
            self.assertIn("CONFIG ERROR:", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
