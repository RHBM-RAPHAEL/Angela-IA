"""Portuguese commands containing English brands: regressions without audio."""
from __future__ import annotations

import unittest
from unittest.mock import Mock
from angela.mixed_language_asr import (
    canonicalize_names, recognized_named_app,
    prefer_better_english_hypothesis,
)
from angela.speech_corrections import correct_transcript
from angela.asr_selection import choose_recognition, configure_command_recognizer
from angela.assistant import AssistantEngine


class FakeChat:
    available = False
    history = []
    def ask(self, message):
        return "CHAT_FALLBACK"


class FakeWindows:
    def __init__(self):
        self.commands = []
        self.pending = None
    def process(self, phrase):
        self.commands.append(phrase)
        if "spotify" in phrase.lower():
            return "Solicitei a abertura de Spotify."
        if "valorant" in phrase.lower():
            return "Solicitei a abertura de VALORANT."
        return None


class MixedLanguageTests(unittest.TestCase):
    def test_phonetic_variants_spotify_and_valorant(self):
        examples = {
            "abra o spotifai": "abra o Spotify",
            "abra o espotifai": "abra o Spotify",
            "abra o esporte fai": "abra o Spotify",
            "abre o spot fy": "abre o Spotify",
            "toque uma música no spotify": "toque uma música no Spotify",
            "inicie o valorante": "inicie o Valorant",
            "abra o valor rante": "abra o Valorant",
            "quero jogar valo rant": "quero jogar Valorant",
            "qual é o jogo valoran": "qual é o jogo Valorant",
            "abre o robloquis": "abre o Roblox",
            "abra o discort": "abra o Discord",
            "abra o istim": "abra o Steam",
            "pesquise no iu tube": "pesquise no YouTube",
        }
        for spoken, expected in examples.items():
            with self.subTest(spoken=spoken):
                self.assertEqual(correct_transcript(spoken), expected)

    def test_pt_portuguese_commands_not_mangled(self):
        for utterance in (
            "qual é o valor da compra?",
            "eu gosto de esportes",
            "abra o esporte",  # ambiguous: still ask to confirm Spotify
            "abra a calculadora",
            "quero abrir o Explorador de Arquivos",
            "vou fazer um curso de programação",
            "sim, pode usar minha câmera",
            "não feche a janela",
            "Valorize é meu projeto",
            "meu cachorro está dormindo",
        ):
            with self.subTest(utterance=utterance):
                self.assertEqual(correct_transcript(utterance), utterance)

    def test_not_take_unrelated_asr_alternative_even_if_near_tie(self):
        cases = (
            ("abra a calculadora", "abra o Spotify"),
            ("abra a câmera", "abra o Valorant"),
            ("feche a calculadora", "abra o Spotify"),
            ("abra o Discord", "abra o Valorant"),
            ("o que é esporte?", "abra o Spotify"),
        )
        for first, next_text in cases:
            with self.subTest(first=first):
                self.assertFalse(prefer_better_english_hypothesis(
                    first, next_text, delta=0.04
                ))

    def test_near_tied_acoustic_alternatives_improve_brand_name(self):
        samples = [
            ("abra o esporte", "abra o spotify", "Spotify"),
            ("abra o valor", "abra o valorant", "Valorant"),
            ("abra o discor", "abra o discord", "Discord"),
        ]
        for first, corrected, name in samples:
            with self.subTest(name=name):
                data = {"alternatives": [
                    {"text": first, "confidence": 0.88},
                    {"text": corrected, "confidence": 0.83},
                ]}
                self.assertEqual(choose_recognition(data), (corrected, True))
                data["alternatives"][1]["confidence"] = 0.50
                self.assertEqual(choose_recognition(data), (first, False))
        recognizer = Mock()
        configure_command_recognizer(recognizer)
        recognizer.SetMaxAlternatives.assert_called_once_with(3)

    def test_known_brand_can_be_recognized_in_question_without_action(self):
        self.assertEqual(
            canonicalize_names("o que você acha do valorante?"),
            "o que você acha do Valorant?"
        )
        self.assertIsNone(recognized_named_app("o que você acha do Spotify?"))
        self.assertEqual(recognized_named_app("abra o Spotifai"), "Spotify")

    def test_ambiguous_esporte_still_requires_confirmation(self):
        engine = AssistantEngine(chat=FakeChat())
        reply = engine.reply("abra o esporte")
        self.assertIn("Você quis dizer Spotify", reply)

    def test_same_sentence_wake_phrase_can_pass_to_bilingual_normalizer(self):
        from angela.wake import WakePhraseParser
        parser = WakePhraseParser()
        event = parser.accept("Ângela, abra o valorante", now=1.0)
        self.assertEqual(event[0], "wake_command")
        self.assertEqual(correct_transcript(event[1]), "abra o Valorant")
        self.assertEqual(
            correct_transcript(parser.accept(
                "Ângela, abra o spotifai", now=2.0
            )[1]), "abra o Spotify"
        )

    def test_routing_mixed_language_to_existing_windows_app_registry(self):
        for spoken, brand in (
            ("abra o espotifai", "Spotify"),
            ("abra o valorante", "VALORANT"),
        ):
            with self.subTest(spoken=spoken):
                windows = FakeWindows()
                engine = AssistantEngine(chat=FakeChat())
                engine.windows = windows
                reply = engine.reply(spoken)
                self.assertIn(brand, reply)
                self.assertTrue(windows.commands)
                self.assertIn(brand.casefold(), windows.commands[-1].casefold())


if __name__ == "__main__":
    unittest.main()
