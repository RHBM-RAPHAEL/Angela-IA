"""Sequence planner tests; no real Windows programs are started."""
import unittest
from unittest.mock import Mock
from angela.sequence_executor import plan_sequence, execute_sequence
from angela.assistant import AssistantEngine


class SequenceTests(unittest.TestCase):
    def test_two_local_actions(self):
        self.assertEqual(plan_sequence("Angela, abra a calculadora e abra o bloco de notas"),
                         [("action", "calculator"), ("action", "notepad")])

    def test_three_steps(self):
        plan = plan_sequence("Abra a calculadora e depois abra o VS Code e abra o explorador")
        self.assertEqual(len(plan), 3)

    def test_unsafe_step_not_planned(self):
        self.assertIsNone(plan_sequence("Abra a calculadora e apague meus arquivos"))
        self.assertIsNone(plan_sequence("Abra a calculadora e execute powershell"))
        self.assertIsNone(plan_sequence("Abra a calculadora e feche o navegador"))

    def test_bound_on_number_of_steps(self):
        self.assertIsNone(plan_sequence("Abra a calculadora e abra o VS Code e abra o bloco de notas e abra o explorador"))

    def test_executes_in_order(self):
        actions = Mock()
        actions.perform.side_effect = ["Abrindo a calculadora.", "Abrindo o Bloco de Notas."]
        windows = Mock()
        windows.pending = None
        result = execute_sequence(plan_sequence("Abra a calculadora e abra o bloco de notas"), actions, windows)
        self.assertIn("Etapa 2", result)
        self.assertEqual(actions.perform.call_count, 2)

    def test_stops_when_step_fails(self):
        actions = Mock()
        actions.perform.side_effect = ["Não consegui abrir.", "Não deve executar."]
        windows = Mock()
        windows.pending = None
        result = execute_sequence(plan_sequence("Abra a calculadora e abra o bloco de notas"), actions, windows)
        self.assertEqual(actions.perform.call_count, 1)
        self.assertIn("não foram executadas", result)

    def test_integrates_with_assistant(self):
        actions = Mock()
        actions.perform.return_value = "Abrindo."
        chat = Mock()
        engine = AssistantEngine(actions=actions, chat=chat)
        response = engine.reply("Abra a calculadora e abra o bloco de notas")
        self.assertIn("Etapa 2", response)
        self.assertEqual(actions.perform.call_count, 2)
        chat.ask.assert_not_called()


if __name__ == "__main__":
    unittest.main()
