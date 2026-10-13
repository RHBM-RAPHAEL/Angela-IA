"""Testes dos mecanismos de voz sem dispositivos reais."""
from unittest import TestCase
from unittest.mock import patch

from angela.speech import SpeechError, VOICE_TEST_SENTENCE, speak


class SpeechTest(TestCase):
    def test_texto_vazio_nao_aciona_voz(self):
        with patch("angela.speech._speak_kokoro") as dora:
            self.assertEqual(speak(" "), "Nenhum texto informado.")
            dora.assert_not_called()

    def test_fala_automatica_prioriza_dora(self):
        with patch("angela.speech._speak_kokoro", return_value="Dora") as dora:
            with patch("angela.speech._speak_windows") as windows:
                self.assertEqual(speak(VOICE_TEST_SENTENCE), "Dora")
                dora.assert_called_once()
                windows.assert_not_called()

    def test_fallback_dora_para_windows(self):
        with patch("angela.speech._speak_kokoro", side_effect=RuntimeError("sem modelo")):
            with patch("angela.speech._speak_windows", return_value="Maria") as local:
                self.assertEqual(speak("Olá"), "Maria")
                local.assert_called_once_with("Olá")

    def test_todos_falham_retorna_diagnostico(self):
        with patch("angela.speech._speak_kokoro", side_effect=RuntimeError("sem modelo")):
            with patch("angela.speech._speak_windows", side_effect=SpeechError("sem voz")):
                with patch("angela.speech._speak_edge", side_effect=SpeechError("403")):
                    with self.assertRaisesRegex(SpeechError, "Confira a saída de som"):
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
            speak("a" * 2200, provider="edge")
            self.assertEqual(len(edge.call_args.args[0]), 1800)
