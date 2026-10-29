"""Etapa 2: interpretação conservadora, confirmação e pedidos incompletos."""
import unittest
from unittest.mock import Mock, patch

from angela.assistant import AssistantEngine
from angela.command_clarification import CommandClarification
from angela.speech_understanding import normalize_intent, unknown_speech
from angela.intent_confirmation import proposed_app


class DummyActions:
    def __init__(self):
        self.calls = []

    def perform(self, name):
        self.calls.append(name)
        return "Ação simulada"


class DummyChat:
    available = False
    def __init__(self):
        self.calls = []

    def ask(self, text):
        self.calls.append(text)
        return "Conversa simulada"


class StageTwoTests(unittest.TestCase):
    def test_natural_variations(self):
        examples = {
            "Você pode abrir a calculadora?": "abra a calculadora",
            "Ângela, eu queria que você abrisse o projeto Valorize": "abra o projeto Valorize",
            "me mostra meus projetos": "mostre meus projetos",
            "eu quero ver meus projetos": "mostre meus projetos",
            "pode me mostrar meus projetos?": "mostre meus projetos",
            "poderia fechar a calculadora?": "feche a calculadora",
        }
        for spoken, expected in examples.items():
            with self.subTest(spoken=spoken):
                self.assertEqual(normalize_intent(spoken), expected)

    def test_questions_are_not_actions(self):
        for spoken in (
            "Como abrir a calculadora?",
            "Você sabe como abrir o VS Code?",
            "Por que fechar o programa?",
            "O que é Python?",
            "me mostra uma explicação de Python",
        ):
            with self.subTest(spoken=spoken):
                self.assertEqual(normalize_intent(spoken), spoken)

    def test_unknown_transcript_does_not_call_ai(self):
        chat = DummyChat()
        engine = AssistantEngine(actions=DummyActions(), chat=chat)
        response = engine.reply("[unk]")
        self.assertIn("Não consegui entender", response)
        self.assertEqual(chat.calls, [])
        self.assertFalse(engine.last_execution)

    def test_clarify_project_then_open_by_name(self):
        engine = AssistantEngine(actions=DummyActions(), chat=DummyChat())
        self.assertIn("Qual projeto", engine.reply("abra o projeto"))
        self.assertFalse(engine.last_execution)
        with patch("angela.assistant.handle_project_request", return_value="Projeto encontrado") as open_project:
            response = engine.reply("Valorize")
        self.assertEqual(response, "Projeto encontrado")
        open_project.assert_called_once()
        self.assertIn("Valorize", open_project.call_args.args[0])
        self.assertTrue(engine.last_execution)

    def test_clarify_app_then_safe_dispatch(self):
        actions = DummyActions()
        engine = AssistantEngine(actions=actions, chat=DummyChat())
        self.assertIn("Qual aplicativo", engine.reply("abra"))
        response = engine.reply("calculadora")
        self.assertEqual(response, "Ação simulada")
        self.assertEqual(actions.calls, ["calculator"])

    def test_clarification_never_interprets_dangerous_reply_as_target(self):
        clock = Mock(return_value=0.0)
        clarifier = CommandClarification(clock)
        clarifier.ask_if_needed("abra o projeto")
        handled, next_command = clarifier.resolve("apague todos os meus arquivos")
        self.assertFalse(handled)
        self.assertIsNone(next_command)
        clarifier.ask_if_needed("abra o projeto")
        handled, next_command = clarifier.resolve("D:\\private\\script.ps1")
        self.assertFalse(handled)
        self.assertIsNone(next_command)
        clarifier.ask_if_needed("abra")
        handled, next_command = clarifier.resolve("não")
        self.assertTrue(handled)
        self.assertIn("cancelei", next_command)

    def test_clarification_expiration(self):
        current = [10.0]
        clarifier = CommandClarification(lambda: current[0])
        clarifier.ask_if_needed("abra o projeto")
        current[0] = 90.0
        handled, answer = clarifier.resolve("Valorize")
        self.assertTrue(handled)
        self.assertIn("expirou", answer)

    def test_spotify_mistranscription_requires_approval(self):
        self.assertEqual(proposed_app("abra o esporte")[0], "Spotify")
        self.assertIsNone(proposed_app("você gosta de esporte?"))
        engine = AssistantEngine(actions=DummyActions(), chat=DummyChat())
        response = engine.reply("poderia abrir o esporte?")
        self.assertIn("Você quis dizer Spotify", response)
        self.assertFalse(engine.last_execution)
        with patch.object(engine.windows, "process", return_value="Solicitei a abertura de Spotify") as proc:
            accepted = engine.reply("sim")
        self.assertIn("Solicitei", accepted)
        proc.assert_called_once_with("abra o spotify")
        self.assertTrue(engine.last_execution)

    def test_engine_normalizes_but_original_is_visible(self):
        actions = DummyActions()
        engine = AssistantEngine(actions=actions, chat=DummyChat())
        result = engine.reply("Você pode abrir a calculadora?")
        self.assertEqual(result, "Ação simulada")
        self.assertEqual(engine.last_interpretation, "abra a calculadora")
        self.assertEqual(actions.calls, ["calculator"])

    def test_planner_http_403_cooldown_does_not_call_api_repeatedly(self):
        from urllib.error import HTTPError
        from angela import agent_planner
        chat = Mock(available=True, model="test", api_key="dummy")
        with patch.object(agent_planner.time, "monotonic", return_value=100), \
             patch.object(agent_planner, "urlopen", side_effect=HTTPError("url", 403, "Forbidden", {}, None)) as remote:
            original = agent_planner._PLANNER_RETRY_AFTER
            try:
                agent_planner._PLANNER_RETRY_AFTER = 0
                self.assertIsNone(agent_planner.plan_via_groq("teste", chat))
                self.assertIsNone(agent_planner.plan_via_groq("teste novamente", chat))
                remote.assert_called_once()
                self.assertEqual(agent_planner._PLANNER_RETRY_AFTER, 700)
            finally:
                agent_planner._PLANNER_RETRY_AFTER = original

    def test_unknown_speech_variants(self):
        self.assertTrue(unknown_speech("[unk]"))
        self.assertTrue(unknown_speech("[unk] [unk]"))
        self.assertFalse(unknown_speech("abra a calculadora"))


if __name__ == "__main__":
    unittest.main()
