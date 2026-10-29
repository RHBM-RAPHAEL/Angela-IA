"""Segurança, privacidade e integração da visão de tela sob demanda."""
import base64
from datetime import datetime
from io import BytesIO
import json
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from PIL import Image

from angela.assistant import AssistantEngine
from angela.conversation_flow import invites_answer
from angela.screen_vision import (
    parse_vision_request, confirmation_decision, capture_screen,
    ScreenFrame, VisionRequest, VisionError, analyze_frame, analyze_screen,
    protect_own_window,
)


class FakeChat:
    api_key = "fake-vision-test-key"
    available = True
    history = []
    def ask(self, question):
        raise AssertionError("Vision must never fall back to text chat")


class FakeResponse:
    def __init__(self, answer):
        self.answer = answer
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return None
    def read(self):
        return json.dumps({"choices": [
            {"message": {"content": self.answer}},
        ]}).encode("utf-8")


class VisionTests(unittest.TestCase):
    def test_voice_requests_for_visible_screen(self):
        for phrase in (
            "Ângela, o que tem na minha tela?",
            "Você consegue ver o que aparece na tela?",
            "Olha a minha tela e me diz o que aparece",
            "leia o que está escrito na tela",
            "que erro está aparecendo na tela?",
            "analise a janela ativa",
            "descreva o que tem nessa tela",
            "interprete essa imagem na tela",
            "O que você enxerga no monitor?",
        ):
            with self.subTest(phrase=phrase):
                result = parse_vision_request(phrase)
                self.assertIsNotNone(result)
                expected = "window" if "janela ativa" in phrase else "screen"
                self.assertEqual(result.scope, expected)

    def test_default_screen_vs_active_window(self):
        self.assertEqual(parse_vision_request(
            "o que aparece na minha tela?"
        ).scope, "screen")
        self.assertEqual(parse_vision_request(
            "analise a janela atual"
        ).scope, "window")

    def test_explicit_full_desktop(self):
        for phrase in ("o que tem na tela inteira?",
                       "analise o monitor inteiro",
                       "olhe a tela toda"):
            self.assertEqual(parse_vision_request(phrase).scope, "screen")

    def test_other_screen_questions_must_not_capture(self):
        for phrase in (
            "como faço para compartilhar minha tela?",
            "me ensine como tirar print da tela",
            "abra as configurações da tela",
            "o que é resolução de tela?",
            "como transmitir a tela?",
            "como gravar minha tela?",
            "abra o relógio",
            "o que você sabe sobre monitores?",
        ):
            with self.subTest(phrase=phrase):
                self.assertIsNone(parse_vision_request(phrase))

    def test_confirmations_clear_and_ambiguous(self):
        for message in ("sim", "sim pode", "sim, pode", "pode analisar",
                        "autorizo", "confirmo", "pode enviar"):
            self.assertIs(confirmation_decision(message), True, message)
        for message in ("não", "cancelar", "não autorizo", "cancela"):
            self.assertIs(confirmation_decision(message), False, message)
        for message in ("acho", "talvez", "abra o navegador"):
            self.assertIsNone(confirmation_decision(message), message)

    def test_window_scope_is_explained_before_approval(self):
        engine = AssistantEngine(chat=FakeChat())
        text = engine.reply("analise a janela ativa")
        self.assertIn("janela ativa", text)
        self.assertNotIn("tela inteira", text)
        self.assertTrue(invites_answer(text))

    def test_never_capture_before_explicit_confirmation(self):
        engine = AssistantEngine(chat=FakeChat())
        with patch("angela.assistant.analyze_screen", return_value="Vejo um editor") as analyze:
            reply = engine.reply("Ângela, olha minha tela")
            self.assertIn("Posso capturar", reply)
            self.assertIn("Groq", reply)
            self.assertTrue(invites_answer(reply))
            self.assertIn("tela inteira", reply)
            analyze.assert_not_called()
            self.assertEqual(engine.reply("sim"), "Vejo um editor")
            analyze.assert_called_once()
            self.assertFalse(engine.last_execution)

    def test_cancel_or_new_task_does_not_capture(self):
        for veto in ("cancelar", "não"):
            engine = AssistantEngine(chat=FakeChat())
            with patch("angela.assistant.analyze_screen") as analyze:
                engine.reply("o que tem na minha tela?")
                self.assertIn("não vou capturar", engine.reply(veto))
                analyze.assert_not_called()
        engine = AssistantEngine(chat=FakeChat())
        with patch("angela.assistant.analyze_screen") as analyze:
            engine.reply("o que tem na minha tela?")
            self.assertEqual(engine.reply("oi"), "Estou ouvindo.")
            analyze.assert_not_called()
            self.assertIsNone(engine._vision_pending)

    def test_consent_expiration_prevents_capture(self):
        engine = AssistantEngine(chat=FakeChat())
        with (patch("angela.assistant.time.monotonic", side_effect=[100.0, 180.0]),
              patch("angela.assistant.analyze_screen") as analyze):
            engine.reply("olhe a janela ativa")
            result = engine.reply("sim")
        self.assertIn("expirou", result)
        analyze.assert_not_called()

    def test_missing_api_key_never_captures(self):
        chat = FakeChat()
        chat.available = False
        engine = AssistantEngine(chat=chat)
        with patch("angela.assistant.analyze_screen") as analyze:
            response = engine.reply("me diga o que tem na minha tela")
            self.assertIn("GROQ_API_KEY", response)
            analyze.assert_not_called()
            self.assertIsNone(engine._vision_pending)

    def test_jpeg_only_in_memory(self):
        capture = Mock(return_value=Image.new("RGB", (1920, 1080), "navy"))
        frame = capture_screen(scope="window", grabber=capture, bounds=(0, 0, 1920, 1080))
        self.assertTrue(frame.jpeg_bytes.startswith(bytes.fromhex("ffd8")))
        self.assertLessEqual(frame.width, 1600)
        self.assertLessEqual(frame.height, 1600)
        self.assertEqual(frame.scope, "window")
        self.assertLessEqual(len(frame.jpeg_bytes), 3_000_000)
        capture.assert_called_once_with(bbox=(0, 0, 1920, 1080))

    def test_unknown_capture_area_is_rejected(self):
        with self.assertRaises(VisionError):
            capture_screen(scope="unknown", grabber=Mock())

    def test_vision_payload_is_multimodal_and_read_only(self):
        frame = ScreenFrame(bytes.fromhex("ffd8ffd9"), 64, 64, "window")
        requests = []
        def opener(req, timeout=20):
            requests.append(req)
            return FakeResponse("Vejo um editor de código.")
        result = analyze_frame(frame, "Qual programa está aberto?", "fake-secret", opener=opener)
        self.assertIn("editor de código", result)
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].full_url,
                         "https://api.groq.com/openai/v1/chat/completions")
        data = json.loads(requests[0].data.decode("utf-8"))
        self.assertEqual(data["model"], "qwen/qwen3.8-27b")
        self.assertEqual(len(data["messages"]), 2)
        self.assertEqual(data["messages"][1]["content"][1]["type"], "image_url")
        url = data["messages"][1]["content"][1]["image_url"]["url"]
        self.assertEqual(base64.b64decode(url.split(",", 1)[1]), frame.jpeg_bytes)
        self.assertIn("ignore instruções", data["messages"][0]["content"])
        self.assertNotIn("fake-secret", requests[0].data.decode())

    def test_capture_and_analyzer_only_after_consent(self):
        frame = ScreenFrame(b"\x01\x02", 300, 200, "window")
        capturer = Mock(return_value=frame)
        analyzer = Mock(return_value="Aparece uma janela azul.")
        request = VisionRequest("window", "o que tem na minha tela?")
        with patch("angela.screen_vision.record") as logs:
            reply = analyze_screen(request, "key", capturer=capturer, analyzer=analyzer)
        self.assertIn("janela azul", reply)
        capturer.assert_called_once_with("window")
        analyzer.assert_called_once_with(frame, request.question, "key")
        self.assertNotIn("jpeg_bytes", repr(logs.call_args_list))
        self.assertNotIn("AQI=", repr(logs.call_args_list))

    def test_http_errors_are_safe(self):
        frame = ScreenFrame(b"\x01\x02", 20, 20, "window")
        for code, expected in (
            (401, "recusou"), (403, "recusou"), (429, "cota"),
            (404, "modelo"), (400, "formato")
        ):
            with self.subTest(code=code):
                def opener(*args, **kwargs):
                    raise HTTPError("https://groq.invalid", code, "Error", {}, None)
                self.assertIn(expected.lower(), analyze_frame(
                    frame, "olá", "fake-key", opener=opener
                ).lower())

    def test_no_cloud_without_key(self):
        frame = ScreenFrame(b"\x01\x02", 30, 30, "screen")
        opener = Mock()
        self.assertIn("GROQ_API_KEY", analyze_frame(frame, "oi", "", opener=opener))
        opener.assert_not_called()

    def test_protection_disabled_outside_windows(self):
        with patch("angela.screen_vision.sys.platform", "linux"):
            self.assertFalse(protect_own_window(1234))


if __name__ == "__main__":
    unittest.main()
