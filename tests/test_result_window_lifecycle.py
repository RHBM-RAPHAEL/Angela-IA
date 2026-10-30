"""Regressao do encerramento inesperado ao fechar a previsao do tempo.

Executa Qt offscreen em processo filho para exercitar QApplication.exec()
sem iniciar a Angela nem ativar microfone/webcam ou abrir janelas no desktop.
"""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import unittest


_SCRIPT = r"""
import sys
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QWidget, QPushButton
from angela.result_window import ResultWindow

app = QApplication([])
app.setQuitOnLastWindowClosed(False)
assert not app.quitOnLastWindowClosed()

# Reproduz a estrutura real: HUD e painel usam Qt.Tool.
overlay = QWidget()
panel = QWidget()
overlay.setWindowFlags(Qt.WindowType.Tool)
panel.setWindowFlags(Qt.WindowType.Tool)
overlay.show()
panel.show()

result = ResultWindow({
    "kind": "weather", "title": "Previsão",
    "subtitle": "Tempo de teste", "text": "Temperatura: 25 graus"
})
assert not result.testAttribute(Qt.WidgetAttribute.WA_QuitOnClose)
result.show()

checkpoints = []
def close_only_result():
    # Exercita o botao Fechar real, nao somente QWidget.close().
    button = next(button for button in result.findChildren(QPushButton)
                  if button.text() == "Fechar")
    button.click()
    checkpoints.append("CLOSED")

def check_still_running():
    assert "CLOSED" in checkpoints
    assert overlay.isVisible()
    assert panel.isVisible()
    checkpoints.append("MAIN_ALIVE")
    print("CHECK_MAIN_ALIVE", flush=True)
    # Encerramento explícito: não pela janela meteorológica.
    app.quit()

QTimer.singleShot(40, close_only_result)
QTimer.singleShot(130, check_still_running)
QTimer.singleShot(1500, lambda: (print("TIMEOUT", flush=True), app.quit()))
app.exec()
assert "MAIN_ALIVE" in checkpoints
print("SUCCESS_RESULT_CLOSE_NO_EXIT", flush=True)
"""


class ResultWindowLifecycleTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "win32", "Aplicativo Qt Windows")
    def test_result_close_keeps_qt_and_tool_windows_alive(self):
        environment = os.environ.copy()
        environment["QT_QPA_PLATFORM"] = "offscreen"
        proc = subprocess.run(
            [sys.executable, "-c", textwrap.dedent(_SCRIPT)],
            env=environment, text=True,
            capture_output=True, timeout=8,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr[:1200])
        self.assertIn("SUCCESS_RESULT_CLOSE_NO_EXIT", proc.stdout)
        self.assertIn("CHECK_MAIN_ALIVE", proc.stdout)

    @unittest.skipUnless(sys.platform == "win32", "Aplicativo Qt Windows")
    def test_result_is_not_considered_quit_window(self):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication
        from angela.result_window import ResultWindow
        application = QApplication.instance() or QApplication([])
        window = ResultWindow({"kind": "weather", "title": "Clima", "text": "teste"})
        self.assertFalse(window.testAttribute(Qt.WidgetAttribute.WA_QuitOnClose))
        self.assertTrue(window.testAttribute(Qt.WidgetAttribute.WA_DeleteOnClose))
        window.close()


if __name__ == "__main__":
    unittest.main()
