"""Regression tests for recorded failures on Oct 31, with no external actions."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch
import unittest

from angela.assistant import AssistantEngine
from angela.camera_mode import contextual_camera_question
from angela.camera_vision import parse_camera_request, camera_question_for_model, clean_camera_analysis
from angela.dialog_context import equation_in_text, solve_linear_equation
from angela.youtube_channels import (
    ALANZOKA_URL, ChannelConversation, known_creator,
    open_known_channel, requested_browser, youtube_channel_request,
)


class Chat:
    available = True
    api_key = "dummy"
    def __init__(self):
        self.history = []
        self.ask = Mock(return_value="Resposta genérica")


class Bridge:
    def is_active(self):
        return True


class RecordedFailuresTests(unittest.TestCase):
    def test_alanzoka_recognized_from_report_variants(self):
        variants = ("alunos oca", "alanzoka", "alanzoca", "alan zoka",
                    "alan zoca", "alunosoca", "alan soca")
        for name in variants:
            with self.subTest(name=name):
                self.assertEqual(known_creator(name), "Alanzoka")
        for other in ("aula", "alunos", "Oracle OCA", "curso de Java"):
            self.assertIsNone(known_creator(other))

    def test_youtube_open_direct_keeps_opera(self):
        request = "abra o canal do youtube do alunos oca no ópera justiça"
        self.assertTrue(youtube_channel_request(request))
        self.assertEqual(requested_browser(request), "opera")
        fake_open = Mock(return_value="Abri o canal do Alanzoka no Opera GX.")
        dialog = ChannelConversation()
        result = dialog.handle(request, open_known=fake_open)
        self.assertIn("Alanzoka", result)
        fake_open.assert_called_once_with(ALANZOKA_URL, "opera")

    def test_youtube_followup_preserves_question(self):
        dialog = ChannelConversation()
        opener = Mock(return_value="Abri o canal do Alanzoka.")
        self.assertIn("Qual canal", dialog.handle(
            "abra o canal do youtube no opera", open_known=opener
        ))
        self.assertIn("Alanzoka", dialog.handle("aula", open_known=opener))
        self.assertEqual(dialog.handle("sim", open_known=opener),
                         "Abri o canal do Alanzoka.")
        opener.assert_called_once_with(ALANZOKA_URL, "opera")

    def test_new_unrelated_topic_does_not_open_previous_channel(self):
        dialog = ChannelConversation()
        opener = Mock()
        dialog.handle("abra o canal do youtube no opera", open_known=opener)
        self.assertIsNone(dialog.handle("como funciona Python?", open_known=opener))
        opener.assert_not_called()

    def test_website_invocation_only_allowlisted_verified_url(self):
        fake_app = SimpleNamespace(
            name="Opera GX", target=r"C:\Fake\Opera\launcher.exe", source="exe"
        )
        fake_windows = Mock()
        fake_windows.catalog.list_apps.return_value = [fake_app]
        proc = Mock()
        with patch("angela.youtube_channels.rank_matches", return_value=[fake_app]):
            result = open_known_channel(
                ALANZOKA_URL, "opera", windows=fake_windows, popen=proc
            )
        self.assertIn("Opera GX", result)
        proc.assert_called_once_with([fake_app.target, ALANZOKA_URL], shell=False)
        proc.reset_mock()
        self.assertIn("Não reconheci", open_known_channel(
            "https://example.com/anything", "opera", windows=fake_windows,
            popen=proc))
        proc.assert_not_called()

    def test_assistant_opens_alanzoka_in_browser_without_chat(self):
        chat = Chat()
        engine = AssistantEngine(chat=chat)
        with patch("angela.assistant.open_known_channel",
                   return_value="Abri o canal do Alanzoka no Opera GX.") as opener:
            response = engine.reply(
                "abra o canal do youtube do alunos oca no ópera justiça"
            )
        self.assertIn("Alanzoka", response)
        opener.assert_called_once_with(
            ALANZOKA_URL, "opera", windows=engine.windows
        )
        chat.ask.assert_not_called()

    def test_followup_short_answer_not_treated_as_oracle(self):
        chat = Chat()
        engine = AssistantEngine(chat=chat)
        with patch("angela.assistant.open_known_channel",
                   return_value="Abri o canal do Alanzoka no Opera.") as opener:
            self.assertIn("Qual canal", engine.reply(
                "abra o canal do youtube no opera"))
            self.assertIn("Alanzoka", engine.reply("aula"))
            self.assertIn("Abri", engine.reply("sim"))
        opener.assert_called_once()
        chat.ask.assert_not_called()

    def test_camera_visual_question_from_log(self):
        self.assertTrue(contextual_camera_question("o que é esse desenho"))
        self.assertTrue(contextual_camera_question("qual é este desenho"))
        self.assertFalse(contextual_camera_question("como desenhar um carro?"))
        self.assertIsNotNone(parse_camera_request("olhe na câmara"))

    def test_live_visual_asks_permission_not_false_inability(self):
        chat = Chat()
        engine = AssistantEngine(chat=chat)
        engine.camera_bridge = Bridge()
        with patch("angela.assistant.analyze_camera") as analyzer:
            reply = engine.reply("o que é esse desenho?")
        self.assertIn("enviar uma foto", reply)
        self.assertIsNotNone(engine._vision_pending)
        analyzer.assert_not_called()
        chat.ask.assert_not_called()

    def test_camera_prompt_references_already_captured_pixels(self):
        self.assertIn("Descreva o desenho",
                      camera_question_for_model("ative a câmera e olhem esse desenho"))
        self.assertIn("Descreva brevemente",
                      camera_question_for_model("olhe na câmara"))
        self.assertIn("equação inteira",
                      camera_question_for_model("olhe essa equação na câmera"))

    def test_remove_only_false_activation_disclaimer_after_capture(self):
        source = ("Não posso ativar a câmera, pois já estou analisando "
                  "a foto que você enviou. Na imagem, vejo um desenho "
                  "de um veículo com rodas.")
        self.assertEqual(clean_camera_analysis(source),
                         "Na imagem, vejo um desenho de um veículo com rodas.")
        self.assertEqual(clean_camera_analysis(
            "Não tenho acesso à câmera e não consegui ver a imagem."
        ), "Não tenho acesso à câmera e não consegui ver a imagem.")

    def test_never_solve_part_of_misread_equation(self):
        ambiguous = 'Na imagem está escrito "3x + 9 = √s10 = x".'
        self.assertIsNone(equation_in_text(ambiguous))
        self.assertEqual(equation_in_text(
            'Uma folha mostra "3x + 9x = x" escrita à mão.'
        ), "3x + 9x = x")
        self.assertIn("x = 0", solve_linear_equation("3x + 9x = x"))

    def test_ambiguous_equation_does_not_hallucinate_solution(self):
        engine = AssistantEngine(chat=Chat())
        engine.visual_context.remember(
            'A foto contém a equação confusa "3x + 9 = √s10 = x".'
        )
        reply = engine.reply("resolva essa equação")
        self.assertIn("Onde está a equação", reply)
        self.assertNotIn("x = 10", reply)


if __name__ == "__main__":
    unittest.main()
