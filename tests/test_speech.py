"""Testes do fallback de voz sem internet e sem dispositivo de áudio."""
from unittest import TestCase
from unittest.mock import patch

from angela.speech import SpeechError, VOICE_TEST_SENTENCE, speak


class SpeechTest(TestCase):
    def test_texto_vazio_nao_aciona_voz(self):
        with patch("angela.speech._speak_edge") as edge:
            self.assertEqual(speak(" "), "Nenhum texto informado.")
            edge.assert_not_called()

    def test_fala_automatica_usa_francisca(self):
        with patch("angela.speech._speak_edge", return_value="Francisca") as edge:
            with patch("angela.speech._speak_windows") as windows:
                self.assertEqual(speak(VOICE_TEST_SENTENCE), "Francisca")
                edge.assert_called_once()
                windows.assert_not_called()

    def test_fallback_quando_rede_falha(self):
        with patch("angela.speech._speak_edge", side_effect=RuntimeError("sem rede")):
            with patch("angela.speech._speak_windows", return_value="Maria") as local:
                self.assertEqual(speak("Olá"), "Maria")
                local.assert_called_once_with("Olá")

    def test_duas_falhas_retorna_diagnostico(self):
        with patch("angela.speech._speak_edge", side_effect=RuntimeError("offline")):
            with patch("angela.speech._speak_windows", side_effect=SpeechError("sem voz")):
                with self.assertRaisesRegex(SpeechError, "Confira a internet"):
                    speak("Olá")

    def test_modo_online_nao_usa_windows(self):
        with patch("angela.speech._speak_edge", return_value="Francisca"):
            with patch("angela.speech._speak_windows") as windows:
                self.assertEqual(speak("Oi", provider="edge"), "Francisca")
                windows.assert_not_called()

    def test_modo_windows_nao_usa_rede(self):
        with patch("angela.speech._speak_edge") as edge:
            with patch("angela.speech._speak_windows", return_value="Maria"):
                self.assertEqual(speak("Oi", provider="windows"), "Maria")
                edge.assert_not_called()

    def test_provedor_invalido(self):
        with self.assertRaises(ValueError):
            speak("Oi", provider="qualquer")

    def test_entrada_limitada(self):
        with patch("angela.speech._speak_edge", return_value="Francisca") as edge:
            speak("a" * 2200)
            self.assertEqual(len(edge.call_args.args[0]), 1800)
