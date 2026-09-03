from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from plan_agent.progress import configure_progress, progress_event


class ProgressTests(unittest.TestCase):
    def tearDown(self) -> None:
        configure_progress(None, console=False)

    def test_neutral_log_is_created_and_flushed_immediately(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "run.log"
            configure_progress(path, console=False)
            progress_event(
                "llm_request_started",
                call_id=1,
                phase="Plan",
                attempt=1,
                attempts=3,
                timeout_seconds=300,
                completion_limit=24_000,
                message_count=1,
            )

            content = path.read_text(encoding="utf-8")
            self.assertIn("event=llm_request_started", content)
            self.assertIn("phase=Plan", content)
            self.assertIn("timeout_seconds=300", content)

    def test_unapproved_fields_cannot_leak_into_neutral_log(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "run.log"
            configure_progress(path, console=False)

            with self.assertRaisesRegex(ValueError, "unapproved field"):
                progress_event("bad_event", prompt="private task text")

            self.assertEqual(path.read_text(encoding="utf-8"), "")


if __name__ == "__main__":
    unittest.main()
