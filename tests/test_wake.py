"""Testes da ativação, sem microfone e sem inferência real."""
import unittest
from unittest.mock import Mock

from angela.wake import WakePhraseParser, WakeListener, extract_wake_command


class WakeParserTest(unittest.TestCase):
    def test_nome_sozinho(self):
        self.assertEqual(extract_wake_command("Ângela"), "")

    def test_nome_com_comando(self):
        self.assertEqual(extract_wake_command("Ângela, abra a calculadora"), "abra a calculadora")

    def test_chamado_oi_angela(self):
        self.assertEqual(extract_wake_command("Oi Ângela!"), "")

    def test_nao_dispara_nome_parecido(self):
        for text in ["evangelho", "angelical", "aquela", "Angele", "abra calculadora"]:
            with self.subTest(text=text):
                self.assertIsNone(extract_wake_command(text))

    def test_ignorar_sem_nome(self):
        self.assertIsNone(WakePhraseParser().accept("abra calculadora", now=0))

    def test_nome_e_depois_comando(self):
        parser = WakePhraseParser()
        self.assertEqual(parser.accept("Ângela", now=1), ("wake_activated", ""))
        self.assertEqual(parser.accept("abra calculadora", now=4), ("wake_command", "abra calculadora"))
        self.assertIsNone(parser.accept("abra bloco", now=5))

    def test_nome_e_comando_na_mesma_frase(self):
        parser = WakePhraseParser()
        self.assertEqual(parser.accept("Ângela mude o tema para claro", now=1),
                         ("wake_command", "mude o tema para claro"))

    def test_expira_apos_oito_segundos(self):
        parser = WakePhraseParser(follow_up_seconds=8)
        parser.accept("Ângela", now=3)
        self.assertFalse(parser.expired(10))
        self.assertTrue(parser.expired(11))
        self.assertFalse(parser.expired(12))
        self.assertIsNone(parser.accept("abra bloco", now=12))

    def test_outra_ativacao_renova_prazo(self):
        parser = WakePhraseParser(follow_up_seconds=8)
        parser.accept("Ângela", now=0)
        parser.accept("Ângela", now=7)
        self.assertEqual(parser.accept("abra calculadora", now=9),
                         ("wake_command", "abra calculadora"))

    def test_reset_cancela_comando_pendente(self):
        parser = WakePhraseParser()
        parser.accept("Ângela", now=1)
        parser.reset()
        self.assertIsNone(parser.accept("abra calculadora", now=2))

    def test_reinicia_apos_resposta_da_dora(self):
        listener = WakeListener(Mock())
        listener.resume(follow_up=True)
        self.assertTrue(listener._followup.is_set())
        self.assertTrue(listener._reset.is_set())

    def test_inicia_desligado(self):
        self.assertFalse(WakeListener(Mock()).running)


if __name__ == "__main__":
    unittest.main()
