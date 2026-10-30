"""Testes do hospedeiro Windows sem ativar microfone ou webcam."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
EXE = ROOT / "launcher" / "AngelaAI" / "bin" / "Release" / "net9.0" / "AngelaAI.exe"


@unittest.skipUnless(sys.platform == "win32", "Inicializador apenas Windows")
@unittest.skipUnless(EXE.is_file(), "Compilar com launcher/build-launcher.ps1")
class BrandedLauncherTests(unittest.TestCase):
    def test_binary_runs_python_312_without_voice(self):
        result = subprocess.run(
            [str(EXE), "-V"], cwd=ROOT, timeout=12,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0, result.stderr[:600])

    def test_python_runs_inside_branded_process(self):
        code = (
            "from pathlib import Path;import sys;"
            "import PySide6,vosk;"
            "assert Path(sys.executable).name == 'AngelaAI.exe';"
            "assert sys.version_info[:2] == (3,12)"
        )
        result = subprocess.run(
            [str(EXE), "-c", code], cwd=ROOT, timeout=16,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0, result.stderr[:600])

    def test_python_subprocess_uses_same_host(self):
        # A captura isolada da camera usa sys.executable -m.
        # Nao abrimos a camera: exercitamos so a substituicao de executavel.
        code = (
            "import sys,subprocess;"
            "result=subprocess.run([sys.executable,'-V'],timeout=8);"
            "assert result.returncode == 0"
        )
        result = subprocess.run(
            [str(EXE), "-c", code], cwd=ROOT, timeout=16,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0, result.stderr[:600])


if __name__ == "__main__":
    unittest.main()
