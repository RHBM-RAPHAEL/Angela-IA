import unittest
from angela.speech_corrections import correct_transcript
from angela.agent_planner import local_fallback_plan
from angela.windows_resources import resource_request


class TestSpeechCorrections(unittest.TestCase):
    def test_english_site(self):
        corrected = correct_transcript("abra o bilhete rabi pelo ópera")
        self.assertEqual(local_fallback_plan(corrected)[0]["target"], "github")

    def test_display_settings(self):
        self.assertEqual(resource_request(correct_transcript("abri as configurações de tela")), ("settings", "ms-settings:display"))

    def test_english_names(self):
        self.assertIn("vs code", correct_transcript("abra o vence code").lower())
        self.assertIn("gmail", correct_transcript("abra o gi mail").lower())
        self.assertIn("bluetooth", correct_transcript("abra as configurações de blututi").lower())

    def test_no_unsafe_guessing(self):
        self.assertEqual(correct_transcript("no se"), "no se")


if __name__ == "__main__":
    unittest.main()
