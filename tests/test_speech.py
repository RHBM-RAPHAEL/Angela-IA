"""Testes de prioridade e fallback da voz, sem dispositivos reais."""
from unittest import TestCase
from unittest.mock import patch
from angela.speech import SpeechError, VOICE_TEST_SENTENCE, speak


class SpeechTest(TestCase):
    def test_texto_vazio_nao_aciona_voz(self):
        with patch("angela.speech._speak_edge") as edge:
            self.assertEqual(speak(" "), "Nenhum texto informado.")
            edge.assert_not_called()

    def test_automatica_prioriza_thalita(self):
        with patch("angela.speech._speak_edge", return_value="Thalita") as edge:
            with patch("angela.speech._speak_kokoro") as dora:
                self.assertEqual(speak(VOICE_TEST_SENTENCE), "Thalita")
                edge.assert_called_once()
                dora.assert_not_called()

    def test_fallback_thalita_para_dora(self):
        with patch("angela.speech._speak_edge", side_effect=SpeechError("sem internet")):
            with patch("angela.speech._speak_kokoro", return_value="Dora") as dora:
                with self.assertRaises(SpeechError):
                    speak("Oi")
                dora.assert_not_called()

    def test_fallback_thalita_e_dora_para_windows(self):
        with patch("angela.speech._speak_edge", side_effect=SpeechError("sem internet")):
            with patch("angela.speech._speak_kokoro", side_effect=RuntimeError("sem modelo")):
                with patch("angela.speech._speak_windows", return_value="Maria") as local:
                    with self.assertRaises(SpeechError):
                        speak("Oi")
                    local.assert_not_called()

    def test_todos_falham_retorna_diagnostico(self):
        with patch("angela.speech._speak_edge", side_effect=SpeechError("403")):
            with patch("angela.speech._speak_kokoro", side_effect=RuntimeError("sem modelo")):
                with patch("angela.speech._speak_windows", side_effect=SpeechError("sem voz")):
                    with self.assertRaisesRegex(SpeechError, "Confira a saída de som"):
                        speak("Olá")

    def test_online_nao_usa_windows(self):
        with patch("angela.speech._speak_edge", return_value="Thalita"):
            with patch("angela.speech._speak_windows") as windows:
                self.assertEqual(speak("Oi", provider="edge"), "Thalita")
                windows.assert_not_called()

    def test_windows_nao_usa_rede(self):
        with patch("angela.speech._speak_edge") as edge:
            with patch("angela.speech._speak_windows", return_value="Maria"):
                self.assertEqual(speak("Oi", provider="windows"), "Maria")
                edge.assert_not_called()

    def test_provedor_invalido(self):
        with self.assertRaises(ValueError):
            speak("Oi", provider="qualquer")

    def test_limite_texto(self):
        with patch("angela.speech._speak_edge", return_value="Thalita") as edge:
            speak("a" * 2200, provider="edge")
            self.assertEqual(len(edge.call_args.args[0]), 1800)
