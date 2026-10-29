"""Tool executor never executes untrusted freeform commands."""
import unittest
from unittest.mock import Mock, patch
from angela.tool_executor import ToolRequest, WindowsToolExecutor, plan_tool
from angela.streaming_tts import split_phrases


class ExecutorTests(unittest.TestCase):
    def test_read_only_plans(self):
        self.assertEqual(plan_tool("Angela, qual o nome do computador"),
                         ToolRequest("read_command", "hostname"))
        self.assertEqual(plan_tool("whoami"), ToolRequest("read_command", "whoami"))

    def test_variacoes_linguagem_natural(self):
        samples = {
            'Angela, qual é o nome do computador?': 'hostname',
            'Me diga qual é a versão do Windows': 'versao do windows',
            'Qual é o meu usuário': 'whoami',
            'Mostre a configuração de rede': 'ipconfig',
        }
        for phrase, target in samples.items():
            with self.subTest(phrase=phrase):
                self.assertEqual(plan_tool(phrase), ToolRequest('read_command', target))

    def test_unknown_not_executed(self):
        self.assertIsNone(plan_tool("apague a pasta Windows"))

    def test_terminal_command_needs_confirmation(self):
        request = plan_tool("execute dir")
        self.assertEqual(request.action, "needs_confirmation")
        runner = Mock()
        reply = WindowsToolExecutor(runner).run(request)
        self.assertIn("analisados", reply)
        runner.assert_not_called()

    def test_allowlisted_command_with_mock(self):
        fake = Mock(returncode=0, stdout="DESKTOP", stderr="")
        runner = Mock(return_value=fake)
        with patch("angela.tool_executor.sys.platform", "win32"):
            reply = WindowsToolExecutor(runner).run(ToolRequest("read_command", "hostname"))
        self.assertEqual(reply, "DESKTOP")
        self.assertEqual(runner.call_args.args[0], ["hostname"])
        self.assertFalse(runner.call_args.kwargs.get("shell", False))

    def test_long_text_split(self):
        phrases = split_phrases("Primeira frase. Segunda frase bem longa para testar.")
        self.assertEqual(len(phrases), 2)
        self.assertEqual(phrases[0], "Primeira frase.")

    def test_no_empty_chunks(self):
        self.assertEqual(split_phrases("   "), [])


if __name__ == "__main__":
    unittest.main()
