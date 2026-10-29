"""Cobertura da etapa 1: feedback opcional, memória e relatório local."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from angela.assistant import AssistantEngine
from angela.feedback_store import (
    save_feedback, record_conversation, recent_conversation, export_report,
)
from angela.voice_coordinator import VoiceCoordinator


class FeedbackStageTests(unittest.TestCase):
    def test_feedback_files_and_redaction(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            history = root / "chat.jsonl"
            feedback = root / "feedback.jsonl"
            record_conversation("user", "minha senha=segredo", history)
            record_conversation("assistant", "Resposta recebida", history)
            save_feedback("abrir projeto", "abriu", True, feedback)
            report = export_report(root / "reports", feedback, history)
            self.assertTrue(report.is_file())
            text = report.read_text(encoding="utf-8")
            self.assertIn("[REDACTED]", text)
            self.assertNotIn("segredo", text)
            self.assertIn("Feedback: SIM", text)
            self.assertEqual(len(recent_conversation(5, history)), 2)

    def test_chat_does_not_request_feedback(self):
        coordinator = VoiceCoordinator(Mock())
        coordinator.active = True
        coordinator.listener = Mock()
        coordinator.on_reply = Mock()
        coordinator.on_feedback_prompt = Mock()
        with patch.object(coordinator, "_speak_async"):
            coordinator.events.put(("execution_reportable", False))
            coordinator.events.put(("reply", "Olá."))
            coordinator.poll()
        self.assertFalse(coordinator.feedback_pending)
        coordinator.on_feedback_prompt.assert_called_with(False)

    def test_execution_requests_visual_feedback_without_speaking_question(self):
        coordinator = VoiceCoordinator(Mock())
        coordinator.active = True
        coordinator.listener = Mock()
        coordinator.on_feedback_prompt = Mock()
        with patch.object(coordinator, "_speak_async") as speak:
            coordinator.events.put(("execution_reportable", True))
            coordinator.events.put(("reply", "Solicitei a abertura da calculadora."))
            coordinator.poll()
        self.assertTrue(coordinator.feedback_pending)
        coordinator.on_feedback_prompt.assert_called_with(True)
        speak.assert_called_once_with("Solicitei a abertura da calculadora.", follow_up=False)

    def test_button_approval_only_when_pending(self):
        coordinator = VoiceCoordinator(Mock())
        coordinator.on_feedback = Mock()
        coordinator.on_feedback_prompt = Mock()
        self.assertFalse(coordinator.accept_feedback(True))
        coordinator.feedback_pending = True
        self.assertTrue(coordinator.accept_feedback(False))
        coordinator.on_feedback.assert_called_once_with(False)
        coordinator.on_feedback_prompt.assert_called_once_with(False)
        self.assertFalse(coordinator.accept_feedback(True))

    def test_voice_feedback_does_not_run_assistant(self):
        coordinator = VoiceCoordinator(Mock())
        coordinator.active = True
        coordinator.listener = Mock()
        coordinator.feedback_pending = True
        coordinator.on_feedback = Mock()
        coordinator.on_feedback_text = Mock()
        coordinator.on_transcript = Mock()
        with patch.object(coordinator, "_reply_async") as reply:
            coordinator.events.put(("wake_command", "não, não era"))
            coordinator.poll()
        coordinator.on_feedback.assert_called_once_with(False)
        coordinator.on_feedback_text.assert_called_once_with("não, não era")
        coordinator.on_transcript.assert_not_called()
        reply.assert_not_called()
        self.assertFalse(coordinator.feedback_pending)

    def test_assistant_marks_actions_not_general_chat(self):
        engine = AssistantEngine()
        self.assertFalse(engine.last_execution)
        engine.reply("bom dia")
        self.assertFalse(engine.last_execution)
        with patch('angela.assistant.list_folders', return_value=['Achei', 'Valorize']):
            answer = engine.reply("quais são os meus projetos?")
        self.assertIn("pastas", answer)
        self.assertTrue(engine.last_execution)


if __name__ == "__main__":
    unittest.main()
