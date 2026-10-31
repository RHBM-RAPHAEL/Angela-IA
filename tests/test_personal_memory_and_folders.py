"""Opt-in private memory and voice folder shortcuts; no real Explorer."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import os
import sys
import threading
import time
import unittest
from unittest.mock import Mock, patch

from angela.personal_memory import PersonalMemory, memory_request
from angela.folder_registry import (
    FolderRegistry, folder_ui_request, folder_alias_request, checked_folder_path,
)
from angela.assistant import AssistantEngine


class Chat:
    available = True
    api_key = "test-only"
    def __init__(self):
        self.history = []
        self.ask = Mock(return_value="Resposta genérica")


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.path = Path(self.tmp.name) / "memory.dat"
        self.memory = PersonalMemory(
            self.path,
            protect=lambda b: b"ENCRYPTED" + b[::-1],
            unprotect=lambda b: b[len(b"ENCRYPTED"):][::-1],
        )
        self.chat = Chat()
        self.engine = AssistantEngine(chat=self.chat)
        self.engine.personal_memory = self.memory

    def tearDown(self):
        self.tmp.cleanup()

    def test_command_recognition_ptbr(self):
        cases = {
            "Salve na memória que meu cachorro chama Thor": ("save", "meu cachorro chama Thor"),
            "salve na memória": ("save", ""),
            "salva na memória que eu gosto de Python": ("save", "eu gosto de Python"),
            "o que você lembra de mim": ("list", ""),
            "apague da memória sobre cachorro": ("forget", "cachorro"),
        }
        for phrase, expected in cases.items():
            with self.subTest(phrase=phrase):
                self.assertEqual(memory_request(phrase), expected)
        self.assertIsNone(memory_request("como funciona memória RAM?"))

    def test_explicit_save_survives_restart_and_does_not_send_to_chat(self):
        reply = self.engine.reply("Salve na memória que meu cachorro chama Thor")
        self.assertIn("Salvei", reply)
        self.assertNotIn(b"cachorro", self.path.read_bytes())
        other = PersonalMemory(self.path, protect=self.memory.protect,
                               unprotect=self.memory.unprotect)
        self.assertEqual(other.all(), ["meu cachorro chama Thor"])
        self.assertIn("cachorro", self.engine.reply("o que você lembra de mim"))
        self.assertIn("Thor", self.engine.reply("qual o nome do meu cachorro?"))
        self.chat.ask.assert_not_called()

    def test_name_memory_answers_name_question_without_cloud(self):
        self.engine.reply("salve na memória que me chamo Rafael")
        self.assertIn("Rafael", self.engine.reply("Qual é o meu nome?"))
        self.chat.ask.assert_not_called()

    def test_two_turn_save_can_be_cancelled(self):
        self.assertIn("O que", self.engine.reply("salve na memória"))
        self.assertTrue(self.engine._personal_memory_pending)
        self.assertIn("Salvei", self.engine.reply("Meu aniversário é em maio"))
        self.assertFalse(self.engine._personal_memory_pending)
        self.assertEqual(self.memory.all(), ["Meu aniversário é em maio"])
        self.engine.reply("salve na memória")
        self.assertIn("Não vou guardar", self.engine.reply("não"))
        self.assertEqual(len(self.memory.all()), 1)

    def test_forget_only_named_subject(self):
        self.engine.reply("salve na memória que meu cachorro chama Thor")
        self.engine.reply("salve na memória que minha cor favorita é azul")
        self.assertIn("Apaguei", self.engine.reply("apague da memória sobre cachorro"))
        self.assertEqual(self.memory.all(), ["minha cor favorita é azul"])
        self.assertIn("qual assunto", self.engine.reply("apague da memória"))

    def test_safeguards_no_credentials_and_no_passive_learning(self):
        self.assertIn("Não consegui salvar", self.engine.reply(
            "salve na memória que minha senha é abc123"))
        self.assertEqual(self.memory.all(), [])
        self.engine.reply("Meu cachorro chama Thor")
        self.assertEqual(self.memory.all(), [])
        with self.assertRaises(ValueError):
            self.memory.add("x" * 300)

    @unittest.skipUnless(sys.platform == "win32", "DPAPI is Windows-only")
    def test_real_windows_dpapi_with_fake_information_only(self):
        path = Path(self.tmp.name) / "dpapi.dat"
        actual = PersonalMemory(path)
        actual.add("meu animal de teste é um lobo de brinquedo")
        self.assertNotIn(b"lobo", path.read_bytes())
        self.assertIn("lobo", PersonalMemory(path).all()[0])


class FolderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.directory = Path(self.tmp.name)
        self.fake_open = Mock()
        self.registry = FolderRegistry(
            self.directory / "alias.json", opener=self.fake_open
        )
        self.engine = AssistantEngine(chat=Chat())
        self.engine.folder_registry = self.registry

    def tearDown(self):
        self.tmp.cleanup()

    def test_commands_open_registry_window(self):
        for phrase in (
            "Ângela, cadastre pastas", "abra gerenciador de pastas",
            "abrir janela de caminhos", "adicionar pasta",
        ):
            self.assertTrue(folder_ui_request(phrase))
        self.assertFalse(folder_ui_request("abra a pasta downloads"))
        self.assertEqual(folder_alias_request("abra a pasta Meus Projetos"),
                         "meus projetos")
        self.assertIsNone(folder_alias_request("que horas são?"))

    def test_ui_request_reaches_voice_event_flag(self):
        self.assertIn("janela para cadastrar", self.engine.reply(
            "Ângela, cadastre pastas"))
        self.assertTrue(self.engine.last_folder_registry_view)
        self.engine.reply("bom dia")
        self.assertFalse(self.engine.last_folder_registry_view)

    def test_save_and_open_alias_without_starting_executable(self):
        target = str(self.directory)
        self.registry.save("Meus Projetos", target)
        self.assertIn("Meus Projetos", self.registry.all())
        second = FolderRegistry(self.registry.path, opener=self.fake_open)
        self.assertEqual(second.resolve("MEUS PROJETOS")[0], "Meus Projetos")
        self.assertIn("Abri", self.engine.reply("abra a pasta meus projetos"))
        self.fake_open.assert_called_once()
        self.assertEqual(self.fake_open.call_args.args[0].casefold(),
                         checked_folder_path(target).casefold())

    def test_no_alias_is_not_intercepted_by_registry(self):
        self.assertIsNone(self.registry.resolve("não existe"))
        self.assertIsNone(self.registry.open_alias("não existe"))
        self.fake_open.assert_not_called()

    def test_injection_and_remote_paths_denied(self):
        for invalid in (
            r"\\some-pc\share", "https://example.com", "calc.exe",
            r"D:\some\missing\folder", r"C:\Windows\system32\cmd.exe",
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    checked_folder_path(invalid)
        self.assertEqual(self.registry.all(), {})

    def test_alias_replacement_and_remove(self):
        self.registry.save("Fotos", str(self.directory))
        self.registry.save("FOTOS", str(self.directory))
        self.assertEqual(len(self.registry.all()), 1)
        self.assertTrue(self.registry.remove("fotos"))
        self.assertFalse(self.registry.remove("fotos"))
        self.assertEqual(self.registry.all(), {})

    @staticmethod
    def _pump_qt_until(app, predicate, seconds=3.0):
        limit = time.monotonic() + seconds
        while not predicate() and time.monotonic() < limit:
            app.processEvents()
            time.sleep(0.01)
        if not predicate():
            raise AssertionError("Qt não processou o evento dentro do prazo")

    def test_qt_window_keeps_processing_events_during_slow_save(self):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication
        from angela.folder_registry_window import FolderRegistryWindow
        app = QApplication.instance() or QApplication([])
        window = FolderRegistryWindow(registry=self.registry)
        started, release = threading.Event(), threading.Event()
        original = self.registry.save
        def slow_save(*args):
            started.set()
            release.wait(2.0)
            return original(*args)
        self.registry.save = slow_save
        try:
            window.alias_edit.setText("Curso de programação")
            window.path_edit.setText(str(self.directory))
            heartbeat = []
            window._save()
            self.assertTrue(started.wait(1))
            QTimer.singleShot(15, lambda: heartbeat.append("Qt responsive"))
            self._pump_qt_until(app, lambda: bool(heartbeat))
            self.assertTrue(window._pending_operation)
            self.assertFalse(window.save_button.isEnabled())
            release.set()
            self._pump_qt_until(app, lambda: not window._pending_operation)
            self.assertEqual(window.listing.count(), 1)
            self.assertIn("Pasta salva", window.status.text())
        finally:
            release.set()
            window.close()

    def test_qt_paste_window_with_simulated_storage(self):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PySide6.QtWidgets import QApplication
        from angela.folder_registry_window import FolderRegistryWindow
        app = QApplication.instance() or QApplication([])
        window = FolderRegistryWindow(registry=self.registry)
        try:
            self.assertIn("caminho da pasta", window.path_edit.accessibleName())
            window.alias_edit.setText("Meus projetos")
            window.path_edit.setText(str(self.directory))
            window._save()
            self._pump_qt_until(app, lambda: not window._pending_operation)
            self.assertIn("Meus projetos", self.registry.all())
            self.assertEqual(window.listing.count(), 1)
            window.listing.setCurrentRow(0)
            window._open()
            self._pump_qt_until(app, lambda: not window._pending_operation)
            self.fake_open.assert_called_once()
            window._remove()
            self._pump_qt_until(app, lambda: not window._pending_operation)
            self.assertEqual(window.listing.count(), 0)
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()
