"""Conversational follow-up and explicit goodbye behavior."""
import unittest
from angela.conversation_flow import invites_answer, wants_to_end
from angela.voice_coordinator import VoiceCoordinator


class ConversationFlowTest(unittest.TestCase):
    def test_follow_up_question(self):
        self.assertTrue(invites_answer("Estou bem! E você, como está?"))
        self.assertFalse(invites_answer("Estou bem, obrigada."))
        self.assertFalse(invites_answer("Não foi possível conectar à IA."))

    def test_goodbye(self):
        for text in ("Tudo certo, obrigado, tchau tchau", "Até logo", "Por hoje é só"):
            self.assertTrue(wants_to_end(text))
        self.assertFalse(wants_to_end("Obrigado pela explicação"))

    def test_follow_up_listens_without_keyword(self):
        states = []
        c = VoiceCoordinator(states.append)
        c.active = True
        c.listener.resume = lambda follow_up=False: states.append(("resume", follow_up))
        c._speak_async = lambda message, follow_up: None
        c.events.put(("reply", "Como você está?"))
        c.poll()
        c.events.put(("finished_speech", "normal"))
        c.poll()
        self.assertIn(("resume", True), states)

    def test_goodbye_stops_followup(self):
        states = []
        c = VoiceCoordinator(states.append)
        c.active = True
        c.listener.pause = lambda: None
        c.listener.resume = lambda follow_up=False: states.append(("resume", follow_up))
        c._reply_async = lambda message: self.fail("should not call AI")
        c.events.put(("wake_command", "Tudo certo, obrigado, tchau tchau"))
        c.poll()
        self.assertTrue(c.conversation_closed)
        self.assertIn(("resume", False), states)


if __name__ == "__main__":
    unittest.main()
