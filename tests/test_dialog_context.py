"""Contextual dialogue without opening webcam, mic or real network."""
from __future__ import annotations

import unittest
from unittest.mock import Mock, patch
from angela.assistant import AssistantEngine
from angela.dialog_context import (
    RecentVisualContext, asks_to_solve_equation, equation_in_text,
    solve_linear_equation, visual_location_reply,
)
from angela.conversation_flow import invites_answer
from angela.voice_coordinator import VoiceCoordinator
from angela.states import AngelaState


class Chat:
    available = True
    api_key = "fake"
    def __init__(self):
        self.history = []
        self.ask = Mock(return_value="Análise simulada.")


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.chat = Chat()
        self.engine = AssistantEngine(chat=self.chat)

    def test_text_from_prior_authorized_photo_solves_equation(self):
        caption = 'A pessoa segura um caderno exibindo a equação "3x + 9x = x".'
        self.assertEqual(equation_in_text(caption), "3x + 9x = x")
        with patch("angela.assistant.analyze_camera", return_value=caption) as capture:
            self.assertEqual(self.engine.reply("olhe pela câmera"),
                             "Posso ativar a câmera e enviar uma foto à IA para análise?")
            capture.assert_not_called()
            self.assertEqual(self.engine.reply("sim"), caption)
            capture.assert_called_once()
        answer = self.engine.reply("resolva essa equação")
        self.assertIn("x = 0", answer)
        self.chat.ask.assert_not_called()

    def test_equations_local_are_correct(self):
        for equation, expected in [
            ("3x + 9x = x", "x = 0"),
            ("2x + 4 = 10", "x = 3"),
            ("x + 2 = 2", "x = 0"),
            ("2x = 2x", "infinitas"),
            ("x = x + 2", "não tem solução"),
            ("2x + 1 = 0", "-1/2"),
        ]:
            with self.subTest(equation=equation):
                self.assertIn(expected, solve_linear_equation(equation))
        self.assertIsNone(solve_linear_equation("import os; os.system('cmd')=1"))
        self.assertIsNone(solve_linear_equation("x**2 = 4"))

    def test_question_about_equation_asks_location_without_capture(self):
        with patch("angela.assistant.analyze_camera") as capture:
            answer = self.engine.reply("resolve essa equação aqui pra mim")
            self.assertIn("Onde está a equação", answer)
            self.assertTrue(self.engine._equation_source_pending)
            capture.assert_not_called()
            self.assertEqual(self.engine.reply("na câmera"),
                             "Posso ativar a câmera e enviar uma foto à IA?")
            capture.assert_not_called()
            self.assertEqual(self.engine._vision_pending[0].scope, "camera")
            self.engine.reply("não")
            capture.assert_not_called()

    def test_one_turn_question_with_camera_still_asks_before_capture(self):
        with patch("angela.assistant.analyze_camera", return_value="x = 3") as capture:
            prompt = self.engine.reply("resolva essa equação aqui. Olha na câmera")
            self.assertIn("ativar a câmera", prompt)
            capture.assert_not_called()
            self.engine.reply("sim")
            capture.assert_called_once()
            self.assertIn("resolva essa equação", capture.call_args.args[0].question)

    def test_context_is_in_memory_expires(self):
        ctx = RecentVisualContext(ttl_seconds=25)
        ctx.remember("Um caderno e uma equação.")
        self.assertEqual(ctx.current(), "Um caderno e uma equação.")
        with patch("angela.dialog_context.time.monotonic", return_value=ctx._at + 26):
            self.assertIsNone(ctx.current())
        self.assertEqual(ctx._text, "")
        self.assertIsNone(self.engine.visual_context.current())

    def test_followup_uses_recent_observation_without_new_capture(self):
        self.engine.visual_context.remember(
            'O caderno mostra a equação 3x + 9x = x.'
        )
        with patch("angela.assistant.analyze_camera") as capture:
            self.engine.reply("qual era a equação que apareceu?")
            capture.assert_not_called()
        self.chat.ask.assert_called_once()
        forwarded = self.chat.ask.call_args.args[0]
        self.assertIn("3x + 9x = x", forwarded)
        self.assertIn("Pergunta:", forwarded)

    def test_unrelated_questions_do_not_receive_visual_caption(self):
        self.engine.visual_context.remember("O caderno mostra 3x + 9x = x.")
        self.engine.reply("O que é Python?")
        self.assertNotIn("3x + 9x = x", self.chat.ask.call_args.args[0])

    def test_camera_only_reply_to_where_is_equation(self):
        self.engine.reply("resolva essa equação")
        with patch("angela.assistant.analyze_camera") as capture:
            prompt = self.engine.reply("câmera")
            self.assertIn("ativar a câmera", prompt)
            capture.assert_not_called()
        self.assertIsNotNone(self.engine._vision_pending)

    def test_no_old_caption_no_automatic_capture(self):
        with patch("angela.assistant.analyze_camera") as capture:
            self.engine.reply("resolva essa equação")
            self.assertIn("pode ditar a equação", self.engine.reply("em outro papel"))
            capture.assert_not_called()

    def test_question_detected_when_statement_follows(self):
        self.assertTrue(invites_answer("Posso ativar a câmera? Diga sim ou não."))
        self.assertTrue(invites_answer("Onde está a equação? Mostre-me."))
        self.assertTrue(invites_answer("Posso capturar a câmera. Responda sim ou não."))
        self.assertFalse(invites_answer("A câmera está desligada."))
        self.assertFalse(invites_answer("O aplicativo não respondeu."))

    def test_microphone_turns_green_only_after_question_spoken(self):
        states = []
        coordinator = VoiceCoordinator(states.append)
        coordinator.active = True
        coordinator.listener = Mock()
        coordinator.engine = Mock(_vision_pending=("camera", 100), _face_pending=None,
                                  _equation_source_pending=False)
        coordinator._speak_async = Mock()
        coordinator.events.put(("reply", "Posso ativar a câmera? Responda sim ou não."))
        coordinator.poll()
        self.assertEqual(states[-1], AngelaState.SPEAKING)
        coordinator.listener.resume.assert_not_called()
        coordinator.events.put(("finished_speech", "normal"))
        coordinator.poll()
        self.assertEqual(states[-1], AngelaState.LISTENING)
        coordinator.listener.resume.assert_called_with(follow_up=True)

    def test_pending_consent_keeps_green_even_no_question_mark(self):
        states = []
        coordinator = VoiceCoordinator(states.append)
        coordinator.active = True
        coordinator.listener = Mock()
        coordinator.engine = Mock(_vision_pending=("camera", 100), _face_pending=None,
                                  _equation_source_pending=False)
        coordinator._speak_async = Mock()
        coordinator.events.put(("reply", "Autorização necessária. Responda sim ou não."))
        coordinator.poll()
        coordinator.events.put(("finished_speech", "normal"))
        coordinator.poll()
        coordinator.listener.resume.assert_called_with(follow_up=True)

if __name__ == "__main__":
    unittest.main()
