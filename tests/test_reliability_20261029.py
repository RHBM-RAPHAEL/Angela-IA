"""Regressões dos problemas observados em conversas reais (28/10).

Os testes não executam ações no PC, não abrem navegadores e não gravam áudio.
"""
import unittest
import sys
from unittest.mock import Mock, patch
from datetime import datetime

from angela.assistant import AssistantEngine
from angela.actions import ActionDispatcher
from angela.command_quality import (
    browser_intent, clock_request, local_clock_reply, normalize_request, speech_summary,
)
from angela.speech_corrections import correct_transcript
from angela.windows_apps import WindowsAppCatalog, rank_matches, InstalledApp
from angela.window_launch import is_window_visible_for


class DummyActions:
    def __init__(self):
        self.calls = []
    def perform(self, name):
        self.calls.append(name)
        return "Solicitei a abertura simulada."


class DummyChat:
    available = False
    def __init__(self):
        self.calls = []
        self.history = [{"role": "assistant", "content": "Contexto antigo sobre Alice"}]
    def ask(self, text):
        self.calls.append(text)
        return "Resposta de conversa simulada"


class ReliabilityTests(unittest.TestCase):
    def test_calculator_requests_without_verb(self):
        actions, chat = DummyActions(), DummyChat()
        engine = AssistantEngine(actions=actions, chat=chat)
        for message in ("calculadora para mim por favor", "calculadora de novo"):
            self.assertIn("simulada", engine.reply(message))
        self.assertEqual(actions.calls, ["calculator", "calculator"])
        self.assertFalse(chat.calls)
        self.assertEqual(chat.history, [])

    def test_vosk_project_aliases(self):
        for phrase in ("alice os meus projetos", "este os meus projetos"):
            with self.subTest(phrase=phrase):
                corrected = correct_transcript(phrase)
                self.assertEqual(corrected, "liste os meus projetos")
                engine = AssistantEngine(actions=DummyActions(), chat=DummyChat())
                with patch("angela.assistant.list_folders", return_value=["Achei", "Valorize"]):
                    self.assertIn("2 pastas", engine.reply(phrase))
                self.assertEqual(engine.last_panel["items"], ["Achei", "Valorize"])

    def test_alice_without_projects_is_not_rewritten(self):
        self.assertEqual(correct_transcript("Alice é minha amiga"), "Alice é minha amiga")

    def test_clock_without_ai(self):
        engine = AssistantEngine(actions=DummyActions(), chat=DummyChat())
        for phrase in ("adivinhe as horas", "apenas me falha as horas", "me fala as horas"):
            with self.subTest(phrase=phrase), patch(
                "angela.assistant.local_clock_reply", return_value="Agora são 09:00."
            ):
                self.assertEqual(engine.reply(phrase), "Agora são 09:00.")
        self.assertEqual(engine.chat.calls, [])
        self.assertEqual(local_clock_reply(datetime(2026, 10, 29, 9, 12)),
                         "Agora são 09:12.")

    def test_browser_negation_asks_not_opens(self):
        chat = DummyChat()
        engine = AssistantEngine(actions=DummyActions(), chat=chat)
        response = engine.reply("abra o youtube não opera")
        self.assertIn("no Opera ou sem o Opera", response)
        self.assertFalse(engine.last_execution)
        self.assertEqual(chat.calls, [])
        self.assertEqual(browser_intent("abra o youtube no opera"), ("youtube", "opera"))

    def test_channel_without_name_requires_target(self):
        engine = AssistantEngine(actions=DummyActions(), chat=DummyChat())
        self.assertIn("nome exato do canal", engine.reply("abraço o canal do youtube do aluno no ópera"))
        self.assertFalse(engine.last_execution)

    def test_general_question_skips_planner(self):
        engine = AssistantEngine(actions=DummyActions(), chat=DummyChat())
        with patch("angela.assistant.plan_via_groq") as planner:
            self.assertEqual(engine.reply("O que é Python?"), "Resposta de conversa simulada")
            planner.assert_not_called()

    def test_action_failure_does_not_request_success_feedback(self):
        engine = AssistantEngine(actions=DummyActions(), chat=DummyChat())
        self.assertIn("não encontrei", engine._as_action("Não encontrei o relógio").lower())
        self.assertFalse(engine.last_execution)

    def test_windows_catalog_json_utf8(self):
        fake_json = '[{"Name":"Relógio","AppID":"Microsoft.WindowsAlarms_8wekyb3d8bbwe!App"}]'
        with patch("angela.windows_apps.subprocess.run",
                   return_value=Mock(returncode=0, stdout=fake_json)) as called:
            items = WindowsAppCatalog._start_apps()
        self.assertEqual(rank_matches(items, "relógio")[0].name, "Relógio")
        self.assertEqual(called.call_args.kwargs["encoding"], "utf-8")
        self.assertIn("UTF8Encoding", called.call_args.args[0][-1])

    def test_confirmed_or_unconfirmed_calculator(self):
        with (patch("angela.actions.sys.platform", "win32"),
              patch("angela.actions.subprocess.Popen"),
              patch("angela.window_launch.wait_for_window", return_value=False)):
            response = ActionDispatcher().perform("calculator")
            self.assertIn("não consegui confirmar", response)
            self.assertNotIn("Confirmei", response)
        with (patch("angela.actions.sys.platform", "win32"),
              patch("angela.actions.subprocess.Popen"),
              patch("angela.window_launch.wait_for_window", return_value=True)):
            response = ActionDispatcher().perform("calculator")
            self.assertIn("Confirmei", response)

    def test_real_window_matching(self):
        self.assertTrue(is_window_visible_for("calculator", [Mock(title="Calculadora")]))
        self.assertFalse(is_window_visible_for("calculator", [Mock(title="Meu navegador")]))

    def test_tts_is_shorter_without_truncating_ui_text(self):
        message = "## **Informações** " + ("Vou explicar os passos em detalhes. " * 25)
        speech = speech_summary(message, limit=290)
        self.assertLess(len(speech), len(message))
        self.assertIn("resposta completa", speech)
        self.assertNotIn("**", speech)

    @unittest.skipUnless(sys.platform == 'win32', 'O overlay gráfico só existe no Windows.')
    def test_feedback_tracks_action_not_yes(self):
        from angela.desktop_overlay import HologramOverlay
        fake = Mock()
        fake.feedback_candidate = ("", "")
        fake.pending_confirmation_command = None
        with patch("angela.desktop_overlay.record_conversation"):
            HologramOverlay.show_transcript(fake, "feche a calculadora")
            HologramOverlay.show_reply(
                fake, "Posso solicitar o fechamento de Calculadora. Confirmar fechamento? Diga sim ou cancelar."
            )
            HologramOverlay.show_transcript(fake, "sim")
            HologramOverlay.show_reply(fake, "Solicitei ao Windows que feche Calculadora.")
        self.assertEqual(fake.feedback_candidate[0], "feche a calculadora")
        self.assertIsNone(fake.pending_confirmation_command)


if __name__ == "__main__":
    unittest.main()
