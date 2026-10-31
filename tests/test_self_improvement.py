"""Self-improvement must only write validated literal rules, never run code."""
from __future__ import annotations
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import unittest

from angela.self_improvement import (
    _parse_rules, apply_rules, learn_correction, learning_request,
    learning_status, load_rules, summarize_feedback,
)
from angela.assistant import AssistantEngine


class FakeChat:
    available = False
    history = []
    def ask(self, _):
        return "Fallback remoto"


class SelfLearningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.rules = Path(self.tmp.name) / "learned_voice_rules.py"
        self.stats = Path(self.tmp.name) / "feedback_summary.json"
        self.rule_path_patch = patch("angela.self_improvement.CODE_PATH", self.rules)
        self.stats_path_patch = patch("angela.self_improvement.ISSUES_PATH", self.stats)
        self.rule_path_patch.start()
        self.stats_path_patch.start()

    def tearDown(self):
        self.rule_path_patch.stop()
        self.stats_path_patch.stop()
        self.tmp.cleanup()

    def test_learning_only_explicit_voice_command(self):
        self.assertEqual(
            learning_request("Ângela, aprenda que espotifau significa Spotify"),
            ("espotifau", "spotify")
        )
        self.assertEqual(
            learning_request("corrija esportifau para Spotify"),
            ("esportifau", "spotify")
        )
        for phrase in (
            "eu gosto de Spotify", "salve na memória que gosto de jogos",
            "como fazer um programa aprender sozinho?",
            "mostre o código da Angela",
        ):
            self.assertIsNone(learning_request(phrase))

    def test_generated_python_data_compiles_without_executing(self):
        result = learn_correction("espotifau", "Spotify")
        self.assertIn("Aprendi", result)
        code = self.rules.read_text(encoding="utf-8")
        compile(code, str(self.rules), "exec")
        self.assertEqual(load_rules(), {"espotifau": "Spotify"})
        self.assertEqual(_parse_rules(code), {"espotifau": "Spotify"})
        self.assertEqual(apply_rules("abra o espotifau"), "abra o Spotify")
        self.assertEqual(apply_rules("abra o bloco de notas"),
                         "abra o bloco de notas")
        self.assertEqual(
            learn_correction("espotifau", "Spotify"),
            "Já aprendi que espotifau significa Spotify."
        )

    def test_multiple_rules_persist_and_only_known_targets(self):
        learn_correction("espotifau", "Spotify")
        learn_correction("valo ranti", "Valorant")
        self.assertEqual(len(load_rules()), 2)
        self.assertEqual(
            apply_rules("abre valo ranti"), "abre Valorant")
        self.assertIn("2 correções", learning_status())
        with self.assertRaises(ValueError):
            learn_correction("browser", "calc.exe")
        with self.assertRaises(ValueError):
            learn_correction("valor", "Valorant")
        with self.assertRaises(ValueError):
            learn_correction("apague", "Spotify")
        with self.assertRaises(ValueError):
            learn_correction("execute powershell", "Spotify")
        self.assertEqual(len(load_rules()), 2)

    def test_malicious_generated_python_cannot_execute(self):
        self.rules.write_text(
            "import os\nos.system('echo dangerous')\n"
            "RULES = {'espotifau': 'Spotify'}\n", encoding="utf-8"
        )
        self.assertEqual(load_rules(), {})
        with self.assertRaises(ValueError):
            learn_correction("valo ranti", "Valorant")
        self.assertIn("import os", self.rules.read_text(encoding="utf-8"))
        with self.assertRaises(ValueError):
            _parse_rules("RULES = __import__('os').system('echo bad')")

    def test_personal_learning_does_not_modify_ordinary_code(self):
        engine = AssistantEngine(chat=FakeChat())
        with patch("angela.assistant.record") as recorder:
            answer = engine.reply(
                "Ângela, aprenda que espotifau significa Spotify"
            )
        self.assertIn("Aprendi", answer)
        self.assertIn("1 correção", engine.reply(
            "Ângela, quantas correções você aprendeu?"
        ))
        from angela.speech_corrections import correct_transcript
        self.assertEqual(correct_transcript("abra o espotifau"), "abra o Spotify")
        recorder.assert_called()

    def test_failed_learning_does_not_write_or_execute(self):
        engine = AssistantEngine(chat=FakeChat())
        answer = engine.reply("aprenda que meu cartão significa Spotify")
        self.assertIn("Não consegui aprender", answer)
        self.assertFalse(self.rules.exists())

    def test_negative_feedback_is_aggregated_not_used_to_modify_code(self):
        for _ in range(3):
            summarize_feedback("abra a camera", False)
        summarize_feedback("abra a camera", True)
        data = json.loads(self.stats.read_text(encoding="utf-8"))
        self.assertEqual(data["camera"], {"total": 4, "failures": 3})
        self.assertIn("camera", learning_status())
        self.assertFalse(self.rules.exists())
        content = self.stats.read_text(encoding="utf-8")
        self.assertNotIn("abra a camera", content)

    def test_feedback_store_hooks_no_private_raw_command_in_summary(self):
        from angela.feedback_store import save_feedback
        feedback_file = Path(self.tmp.name) / "feedback.jsonl"
        # Explicit test file should not aggregate into the actual user's stats.
        save_feedback("abra a calculadora", "Não abriu", False, feedback_file)
        self.assertTrue(feedback_file.is_file())
        self.assertFalse(self.rules.exists())
        # Summary is aggregated and contains no user prompt.
        if self.stats.exists():
            self.assertNotIn("abra a calculadora",
                             self.stats.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
