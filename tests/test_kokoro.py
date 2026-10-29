"""Testes das opções de voz. Não acessam rede nem baixam modelos."""
import unittest
from unittest.mock import patch

from angela.kokoro_local import files_available
from angela.speech import SpeechError, _friendly_error, speak
from angela.chat import DEFAULT_MODEL, GroqChat, select_model


class TestKokoro(unittest.TestCase):
    def setUp(self):
        import os
        flag = patch.dict(os.environ, {"ANGELA_TTS_STREAMING": "0"})
        flag.start()
        self.addCleanup(flag.stop)

    def test_arquivos_ausentes(self):
        with patch("angela.kokoro_local.MODEL_FILE") as model:
            model.is_file.return_value = False
            self.assertFalse(files_available())

    def test_fala_dora(self):
        with patch("angela.speech._speak_kokoro", return_value="Dora") as dora:
            with patch("angela.speech._speak_edge") as edge:
                self.assertEqual(speak("Olá", "kokoro"), "Dora")
                dora.assert_called_once_with("Olá")
                edge.assert_not_called()

    def test_automatico_prioriza_thalita(self):
        with patch("angela.speech._speak_kokoro") as dora:
            with patch("angela.speech._speak_windows") as windows:
                with patch("angela.speech._speak_edge", return_value="Thalita") as edge:
                    self.assertEqual(speak("Oi", "auto"), "Thalita")
                    windows.assert_not_called()
                    dora.assert_not_called()
                    edge.assert_called_once()

    def test_automatico_windows_se_edge_e_dora_falharem(self):
        with patch("angela.speech._speak_kokoro", side_effect=RuntimeError("sem modelo")):
            with patch("angela.speech._speak_windows", return_value="Windows"):
                with patch("angela.speech._speak_edge", side_effect=SpeechError("sem internet")):
                    with self.assertRaises(SpeechError):
                        speak("Oi", "auto")

    def test_automatico_francisca_por_ultimo(self):
        with patch("angela.speech._speak_kokoro", side_effect=RuntimeError("sem modelo")):
            with patch("angela.speech._speak_windows", side_effect=RuntimeError("sem SAPI")):
                with patch("angela.speech._speak_edge", return_value="Francisca"):
                    self.assertEqual(speak("Oi", "auto"), "Francisca")

    def test_nao_expoe_url_token_da_edge(self):
        exc = RuntimeError("403 wss://servidor/?TrustedClientToken=SEGREDO")
        message = _friendly_error("edge", exc)
        self.assertNotIn("SEGREDO", message)
        self.assertNotIn("wss://", message)

    def test_falha_de_todos_provedores_e_resumo(self):
        with patch("angela.speech._speak_kokoro", side_effect=RuntimeError("sem modelo")):
            with patch("angela.speech._speak_windows", side_effect=RuntimeError("sem voz")):
                with patch("angela.speech._speak_edge", side_effect=SpeechError("403")):
                    with self.assertRaises(SpeechError) as ctx:
                        speak("Oi", "auto")
                    self.assertNotIn("Dora:", str(ctx.exception))
                    self.assertIn("Francisca:", str(ctx.exception))

    def test_modelo_groq_legado_migrado(self):
        self.assertEqual(select_model("llama-3.3-70b-versatile"), DEFAULT_MODEL)
        self.assertEqual(select_model("llama-3.1-8b-instant"), DEFAULT_MODEL)

    def test_outros_modelos_respeitados(self):
        self.assertEqual(select_model("qwen/qwen3.8-27b"), "qwen/qwen3.8-27b")

    def test_groq_api_key_nao_aparece_no_texto_de_modelo(self):
        chat = GroqChat(api_key="KEY_NAO_EXIBIR", model="llama-3.3-70b-versatile")
        self.assertTrue(chat.available)
        self.assertEqual(chat.model, DEFAULT_MODEL)


if __name__ == "__main__":
    unittest.main()
