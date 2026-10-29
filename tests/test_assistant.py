"""Testes sem acesso ao Windows, rede, microfone ou dispositivo de áudio."""
import unittest

from angela.actions import detect_action, normalize
from angela.assistant import AssistantEngine


class DummyActions:
    def __init__(self):
        self.seen = []

    def perform(self, action):
        self.seen.append(action)
        return "Ação simulada"


class DummyChat:
    def __init__(self):
        self.seen = []

    def ask(self, message):
        self.seen.append(message)
        return "Resposta simulada"


class TestActions(unittest.TestCase):
    def test_acao_windows_claro(self):
        self.assertEqual(detect_action("Ângela, mude o tema do Windows para claro"), "theme_light")

    def test_acao_windows_escuro(self):
        self.assertEqual(detect_action("Coloque no modo escuro"), "theme_dark")

    def test_aplicativos(self):
        examples = {
            "Abra a calculadora": "calculator",
            "Abre o bloco de notas": "notepad",
            "Abra o explorador de arquivos": "explorer",
            "Abra o VS Code": "vscode",
        }
        for text, action in examples.items():
            with self.subTest(text=text):
                self.assertEqual(detect_action(text), action)

    def test_acao_nao_permitida(self):
        self.assertIsNone(detect_action("Execute rm -rf /"))
        self.assertIsNone(detect_action("Apague todas as minhas pastas"))
        self.assertIsNone(detect_action("Como mudar o tema claro?"))

    def test_normalizacao(self):
        self.assertEqual(normalize("ÂNGELA"), "angela")

    def test_roteamento_acao(self):
        actions, chat = DummyActions(), DummyChat()
        answer = AssistantEngine(actions=actions, chat=chat).reply("Abra a calculadora")
        self.assertEqual(answer, "Ação simulada")
        self.assertEqual(actions.seen, ["calculator"])
        self.assertEqual(chat.seen, [])

    def test_frases_variadas_calculadora(self):
        phrases = ("Angela, abra a calculadora", "Pode abrir a calculadora", "Você consegue abrir a calculadora", "Calculadora", "calculadora para mim")
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                self.assertEqual(detect_action(phrase), "calculator")

    def test_novo_comando_interrompe_escolha_pendente(self):
        from angela.windows_controller import Pending
        import time
        actions, chat = DummyActions(), DummyChat()
        engine = AssistantEngine(actions=actions, chat=chat)
        engine.windows.pending = Pending('choose_app', [], time.monotonic() + 90)
        self.assertEqual(engine.reply('Abra a calculadora'), 'Ação simulada')
        self.assertIsNone(engine.windows.pending)

    def test_roteamento_chat(self):
        actions, chat = DummyActions(), DummyChat()
        answer = AssistantEngine(actions=actions, chat=chat).reply("O que é Python?")
        self.assertEqual(answer, "Resposta simulada")
        self.assertEqual(actions.seen, [])
        self.assertEqual(chat.seen, ["O que é Python?"])

    def test_saudacao(self):
        self.assertIn("ouvindo", AssistantEngine(chat=DummyChat()).reply("Olá"))


if __name__ == "__main__":
    unittest.main()
