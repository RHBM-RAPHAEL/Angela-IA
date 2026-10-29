import tempfile
import unittest
from pathlib import Path
from angela.adaptive_memory import preference_request, save_preference, load_preferences
from angela.speech_corrections import correct_transcript
from angela.project_listing import list_request

class TestAdaptiveMemory(unittest.TestCase):
    def test_preferences(self):
        self.assertEqual(preference_request('fale pouco'), ('short_answers', True))
        self.assertEqual(preference_request('fale normalmente'), ('short_answers', False))
        self.assertIsNone(preference_request('apague meu projeto'))
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'prefs.json'
            self.assertTrue(save_preference('short_answers', True, path)['short_answers'])
            self.assertTrue(load_preferences(path)['short_answers'])
            with self.assertRaises(ValueError):
                save_preference('privileged_commands', True, path)

    def test_speech_corrections_are_contextual(self):
        for phrase in ('este os projetos que eu tenho na pasta meus software',
                       'list os projetos que eu tenho na pasta meu software',
                       'lixo e quase projetos eu tenho na pasta de meu software'):
            self.assertIsNotNone(list_request(correct_transcript(phrase)))
        self.assertEqual(correct_transcript('este arquivo é importante'), 'este arquivo é importante')
