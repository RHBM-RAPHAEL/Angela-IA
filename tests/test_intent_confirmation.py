import unittest
from angela.intent_confirmation import IntentConfirmation, proposed_app
from angela.user_profile import PROFILE
from angela.assistant import AssistantEngine


class DummyActions:
    def __init__(self):
        self.calls = []
    def perform(self, name):
        self.calls.append(name)
        return "Ação simulada"


class DummyChat:
    available = False
    def ask(self, message):
        return "Conversa simulada"


class IntentConfirmationTests(unittest.TestCase):
    def test_suspected_app(self):
        self.assertEqual(proposed_app("abra o Virtual Studio Code")[0], "Visual Studio Code")
        self.assertEqual(proposed_app("abra o viesse code")[0], "Visual Studio Code")
        self.assertIsNone(proposed_app("o que é Virtual Studio Code?"))

    def test_confirm_before_open(self):
        actions = DummyActions()
        engine = AssistantEngine(actions=actions, chat=DummyChat())
        answer = engine.reply("abra o virtual studio code")
        self.assertIn("Você quis dizer Visual Studio Code", answer)
        self.assertEqual(actions.calls, [])
        self.assertEqual(engine.reply("sim"), "Ação simulada")
        self.assertEqual(actions.calls, ["vscode"])

    def test_cancel_and_new_request(self):
        actions = DummyActions()
        engine = AssistantEngine(actions=actions, chat=DummyChat())
        engine.reply("abra o virtual studio code")
        self.assertIn("não vou abrir", engine.reply("não"))
        self.assertEqual(actions.calls, [])

    def test_profile(self):
        self.assertEqual(PROFILE["name"], "Rafael")
        self.assertEqual(PROFILE["age"], 21)

if __name__ == "__main__":
    unittest.main()
