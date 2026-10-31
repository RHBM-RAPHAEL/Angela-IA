"""Windows login autostart: script structure and read-only prerequisite check.

Never enables/disables startup as part of automated tests, and does not
start additional GUI processes or use real microphone hardware.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
LAUNCHER = ROOT / "launcher"
START = LAUNCHER / "start-with-windows.ps1"
CONFIG = LAUNCHER / "configure-startup.ps1"


class WindowsStartupTests(unittest.TestCase):
    def test_script_guards_duplicate_process_and_local_hud(self):
        startup = START.read_text(encoding="utf-8")
        self.assertIn("Get-Process -Name AngelaAI", startup)
        self.assertIn("ALREADY_RUNNING", startup)
        self.assertIn("127.0.0.1:18766", startup)
        self.assertIn("angela\\web", startup)
        self.assertIn("ANGELA_ENABLE_VOICE = '1'", startup)
        self.assertIn("ANGELA_START_ON_LOGIN", startup)
        self.assertIn("Start-Process -FilePath $exe", startup)
        self.assertIn("Write-StartupLog", startup)

    def test_installer_is_per_user_and_reversible(self):
        config = CONFIG.read_text(encoding="utf-8")
        self.assertIn("GetFolderPath('Startup')", config)
        self.assertIn("start-with-windows.ps1", config)
        self.assertIn("-NoProfile -NonInteractive -WindowStyle Hidden", config)
        self.assertIn("Remove-Item -LiteralPath $shortcutPath", config)
        self.assertIn("if ($Disable)", config)
        self.assertIn("if ($Status)", config)
        self.assertIn("if (-not ($Enable -or $Disable -or $Status))", config)
        self.assertNotIn("HKLM:", config)
        self.assertNotIn("schtasks /create", config.lower())

    @unittest.skipUnless(sys.platform == "win32", "Windows-only startup")
    def test_requirements_without_starting_app(self):
        result = subprocess.run([
            "powershell.exe", "-NoProfile", "-NonInteractive",
            "-ExecutionPolicy", "Bypass", "-File", str(START),
            "-VerifyOnly"
        ], capture_output=True, text=True, timeout=12)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("STARTUP_PREREQUISITES_OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
