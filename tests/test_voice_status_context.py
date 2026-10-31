"""Regressões dos relatos de 31/10; nunca abre câmera, microfone ou rede."""
from __future__ import annotations

import unittest
from unittest.mock import Mock, patch
from angela.assistant import AssistantEngine
from angela.command_quality import voice_status_request
from angela.chat import SYSTEM_PROMPT


class FakeChat:
    available = True
    api_key = "test"
    def __init__(self):
        self.history = []
        self.ask = Mock(return_value="MODELO_REMOTO_NAO_TEM_MICROFONE")


class VoiceStatusContextTests(unittest.TestCase):
    def setUp(self):
        self.chat = FakeChat()
        self.engine = AssistantEngine(chat=self.chat)

    def test_voice_status_from_registered_transcript_never_calls_llm(self):
        for phrase in [
            "você está ouvindo a minha voz",
            "você me ouve",
            "você consegue me ouvir",
            "você tá me escutando",
            "está ouvindo minha voz",
        ]:
            with self.subTest(phrase=phrase):
                answer = self.engine.reply(phrase)
                self.assertIn("recebendo o que você fala", answer)
                self.assertIn("reconhecimento de voz", answer)
                self.chat.ask.assert_not_called()

    def test_unrelated_questions_preserved(self):
        for phrase in [
            "como funciona o microfone",
            "você sabe como configurar um microfone USB",
            "explique as diferenças de gravação de áudio",
            "não consigo ouvir o áudio do meu jogo",
        ]:
            with self.subTest(phrase=phrase):
                self.assertFalse(voice_status_request(phrase))
        self.assertIn("microfone e reconhecimento de voz local", SYSTEM_PROMPT)

    def test_uncertain_yes_keeps_face_consent_pending_without_camera(self):
        fake = Mock()
        fake.enrolled.return_value = True
        self.engine.face_profile = fake
        with patch("angela.camera_vision.capture_camera") as camera:
            ask = self.engine.reply("Você me conhece pela câmera?")
            self.assertIn("Você autoriza", ask)
            unclear = self.engine.reply("assim")
            self.assertIn("Não entendi sua resposta", unclear)
            self.assertEqual(self.engine._face_pending[0], "recognize")
            camera.assert_not_called()
            self.engine.reply("não")
            self.assertIsNone(self.engine._face_pending)
            camera.assert_not_called()

    def test_uncertain_yes_does_not_allow_screen_or_camera_capture(self):
        with patch("angela.camera_vision.capture_camera") as camera:
            ask = self.engine.reply("abra a câmera e me veja")
            self.assertIn("Você autoriza", ask)
            unclear = self.engine.reply("assim")
            self.assertIn("Diga sim", unclear)
            self.assertIsNotNone(self.engine._vision_pending)
            camera.assert_not_called()
            self.assertIn("não vou ligar", self.engine.reply("não"))
            camera.assert_not_called()

    def test_unrelated_command_cancels_pending_permission(self):
        fake = Mock()
        fake.enrolled.return_value = True
        self.engine.face_profile = fake
        with patch("angela.camera_vision.capture_camera") as camera:
            self.engine.reply("Você me conhece pela câmera?")
            self.engine.reply("Que horas são agora?")
            self.assertIsNone(self.engine._face_pending)
            camera.assert_not_called()

    def test_short_consent_is_not_implicitly_approved(self):
        self.assertFalse(voice_status_request("assim"))
        fake = Mock()
        fake.enrolled.return_value = True
        self.engine.face_profile = fake
        with patch("angela.camera_vision.capture_camera") as camera:
            self.engine.reply("Você me reconhece pela câmera?")
            self.engine.reply("assim")
            camera.assert_not_called()


if __name__ == "__main__":
    unittest.main()
