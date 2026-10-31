"""Live camera mode regression tests. No real camera or network calls."""
from __future__ import annotations

import os
import sys
import threading
import unittest
from unittest.mock import Mock, patch

from angela.assistant import AssistantEngine
from angela.camera_mode import camera_mode_command, contextual_camera_question


class Chat:
    available = True
    api_key = "fake"
    def __init__(self):
        self.history = []
    def ask(self, message):
        return "Resposta simulada."


class FakeBridge:
    def __init__(self):
        self.active = False
        self.open_count = 0
        self.close_count = 0
        self.snapshot_count = 0

    def open(self):
        self.active = True
        self.open_count += 1
        return True

    def close(self):
        previous = self.active
        self.active = False
        self.close_count += 1
        return previous

    def is_active(self):
        return self.active

    def snapshot(self):
        self.snapshot_count += 1
        from PIL import Image
        from io import BytesIO
        image = Image.new("RGB", (480, 360), (18, 55, 85))
        stream = BytesIO()
        image.save(stream, format="JPEG")
        return stream.getvalue()


class LiveCameraIntentsTests(unittest.TestCase):
    def setUp(self):
        self.engine = AssistantEngine(chat=Chat())
        self.bridge = FakeBridge()
        self.engine.camera_bridge = self.bridge

    def test_activation_and_close_phrases_only(self):
        for utterance in [
            "Ângela, ative a visão computacional",
            "ative visão computacional",
            "ligue a visão computacional",
            "abrir visão computacional",
            "iniciar visão computacional",
        ]:
            with self.subTest(utterance=utterance):
                self.assertEqual(camera_mode_command(utterance), "open")
        for phrase in [
            "feche a câmera", "desative a visão computacional",
            "desligue a webcam", "fechar câmera",
        ]:
            self.assertEqual(camera_mode_command(phrase), "close")
        for phrase in [
            "como funciona a visão computacional",
            "ative as configurações computacionais",
            "o que a câmera está vendo",
            "como configurar a câmera",
            "ative a calculadora",
        ]:
            self.assertIsNone(camera_mode_command(phrase))

    def test_ui_opens_only_when_explicitly_requested(self):
        self.assertFalse(self.bridge.is_active())
        self.assertIn("ativada", self.engine.reply("ative a visão computacional"))
        self.assertTrue(self.bridge.is_active())
        self.assertEqual(self.bridge.open_count, 1)
        self.assertIn("ativada", self.engine.reply("ative visão computacional"))
        self.assertEqual(self.bridge.open_count, 2)
        self.assertIn("fechada", self.engine.reply("feche a câmera"))
        self.assertFalse(self.bridge.is_active())

    def test_live_contextual_requests_are_scoped_to_preview(self):
        self.engine.reply("ative a visão computacional")
        for phrase in [
            "o que você está vendo?", "veja isso aqui",
            "leia essa equação", "qual é a cor aqui",
        ]:
            with self.subTest(phrase=phrase):
                with patch("angela.assistant.analyze_camera") as analyze:
                    prompt = self.engine.reply(phrase)
                    self.assertEqual(self.engine._vision_pending[0].scope, "camera")
                    self.assertIn("enviar uma foto", prompt)
                    analyze.assert_not_called()
                    self.engine.reply("não")
                    analyze.assert_not_called()

    def test_unrelated_request_never_triggers_camera_capture(self):
        self.engine.reply("ative a visão computacional")
        for phrase in ["Que horas são?", "Como funciona Python?", "Abra a calculadora"]:
            self.assertFalse(contextual_camera_question(phrase))
        self.assertFalse(contextual_camera_question("como funciona o reconhecimento facial"))

    def test_explicit_yes_reuses_preview_camera_not_second_camera(self):
        self.engine.reply("ative a visão computacional")
        with patch("angela.assistant.analyze_camera", return_value="Vejo um livro.") as analyzer:
            self.engine.reply("olhe o que eu estou segurando pela câmera")
            self.assertEqual(self.bridge.snapshot_count, 0)
            result = self.engine.reply("sim")
            self.assertEqual(result, "Vejo um livro.")
            self.assertEqual(analyzer.call_count, 1)
            capturer = analyzer.call_args.kwargs["capturer"]
            with patch("angela.camera_vision._isolated_capture_frame") as separate:
                frame = capturer()
                self.assertEqual(frame.scope, "camera")
                self.assertGreater(len(frame.jpeg_bytes), 100)
                separate.assert_not_called()
            self.assertEqual(self.bridge.snapshot_count, 1)

    def test_decline_does_not_read_preview_or_send_picture(self):
        self.engine.reply("ative a visão computacional")
        with patch("angela.assistant.analyze_camera") as analyzer:
            self.engine.reply("o que você está vendo?")
            self.assertIn("não vou ligar", self.engine.reply("não"))
            self.assertEqual(self.bridge.snapshot_count, 0)
            analyzer.assert_not_called()

    def test_close_cancels_pending_remote_analysis(self):
        self.engine.reply("ative a visão computacional")
        self.engine.reply("o que você está vendo?")
        self.assertIsNotNone(self.engine._vision_pending)
        self.engine.reply("feche a câmera")
        self.assertIsNone(self.engine._vision_pending)
        self.assertFalse(self.bridge.is_active())
        with patch("angela.assistant.analyze_camera") as analyzer:
            self.engine.reply("sim")
            analyzer.assert_not_called()

    def test_closing_in_gui_is_reflected_in_engine(self):
        self.engine.reply("ative a visão computacional")
        self.bridge.active = False  # button/window close
        with patch("angela.assistant.analyze_camera") as analyzer:
            self.assertIsNone(self.engine._vision_pending)
            answer = self.engine.reply("o que você está vendo?")
            self.assertNotIn("enviar uma foto da câmera", answer)
            analyzer.assert_not_called()


@unittest.skipUnless(sys.platform == "win32", "Qt preview is Windows only")
class PreviewBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_bridge_threaded_open_snapshot_close_mock_camera(self):
        from PySide6.QtCore import QObject, Signal
        from PySide6.QtWidgets import QWidget
        from angela.camera_preview import CameraPreviewBridge
        from angela.camera_mode import camera_mode_command

        class DummyWindow(QWidget):
            closed = Signal()
            failed = Signal(str)
            def __init__(self):
                super().__init__()
                self.started = False
            def start(self):
                self.started = True
                self.show()
            def capture_jpeg(self):
                return b"simulated-jpeg-data"
            def closeEvent(self, event):
                self.closed.emit()
                super().closeEvent(event)

        bridge = CameraPreviewBridge(window_factory=DummyWindow)
        outputs = []
        def worker():
            outputs.append(bridge.open())
            outputs.append(bridge.is_active())
            outputs.append(bridge.snapshot())
            outputs.append(bridge.close())

        thread = threading.Thread(target=worker)
        thread.start()
        from time import monotonic, sleep
        deadline = monotonic() + 5
        while thread.is_alive() and monotonic() < deadline:
            self.app.processEvents()
            sleep(0.01)
        thread.join(timeout=0.1)
        self.assertFalse(thread.is_alive(), "Qt event dispatcher blocked")
        self.assertEqual(outputs, [True, True, b"simulated-jpeg-data", True])
        self.assertFalse(bridge.is_active())
        bridge.deleteLater()
