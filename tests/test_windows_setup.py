from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class WindowsSetupTests(unittest.TestCase):
    def test_uv_resolution_uses_one_application_path(self) -> None:
        script = (ROOT / "setup_windows.ps1").read_text(encoding="utf-8")

        self.assertIn("Get-Command uv.exe -CommandType Application", script)
        self.assertIn("Select-Object -First 1", script)
        self.assertIn("return [string]$UvCommand.Path", script)
        self.assertIn("& $UvExecutable venv", script)
        self.assertNotIn("$UvCommand.Source", script)

    def test_explicit_uv_path_is_supported(self) -> None:
        script = (ROOT / "setup_windows.ps1").read_text(encoding="utf-8")

        self.assertIn('[string]$UvPath = ""', script)
        self.assertIn("Test-Path -LiteralPath $RequestedPath -PathType Leaf", script)


if __name__ == "__main__":
    unittest.main()
