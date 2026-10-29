"""Valida componentes Qt em memoria: nao abre nem inicia a Angela."""
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPlainTextEdit
from angela.result_window import ResultWindow


class ResultWindowQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._application = QApplication.instance() or QApplication([])

    def test_text_view_is_plain_text_and_read_only(self):
        untrusted = "<script>alert('x')</script>\n**Isto nao deve ser HTML**"
        view = ResultWindow({
            "kind": "text", "title": "Informações",
            "subtitle": "Resumo", "text": untrusted,
        })
        editor = view.findChild(QPlainTextEdit, "result-text")
        self.assertIsNotNone(editor)
        self.assertTrue(editor.isReadOnly())
        self.assertEqual(editor.toPlainText(), untrusted)
        self.assertIn("Informações", view.windowTitle())
        view.close()

    def test_weather_view_no_browser(self):
        view = ResultWindow({
            "kind": "weather", "title": "Clima",
            "subtitle": "25 graus", "text": "Próximos dias",
            "source": "Open-Meteo",
        })
        self.assertIsNone(view.video_view)
        self.assertEqual(view.findChild(QPlainTextEdit, "result-text").toPlainText(), "Próximos dias")
        view.close()

    def test_reject_untrusted_result_types(self):
        with self.assertRaises(ValueError):
            ResultWindow({"kind": "script", "text": "exec"})
        with self.assertRaises(ValueError):
            ResultWindow({"kind": "video", "url": "https://evil.test/"})
