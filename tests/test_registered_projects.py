"""Recorded 31 Oct voice transcripts -> saved folder -> VS Code.

No real app launches. Must never open unrelated commands or unknown paths.
"""
from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from angela.assistant import AssistantEngine
from angela.folder_registry import FolderRegistry
from angela.project_tools import Project, find_vscode
from angela.registered_projects import registered_project_alias, open_registered_project


class FakeChat:
    available = True
    api_key = "fake"
    history = []
    def ask(self, text):
        return "CHAT_REPLY"


class SavedProjectsTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.aliases = FolderRegistry(Path(self.temp.name) / "folders.json", opener=Mock())
        self.folder = Path(self.temp.name)
        self.aliases.save("Curso", str(self.folder))
        self.runner = Mock(return_value="Enviei o projeto Curso para o VS Code.")
    def tearDown(self):
        self.temp.cleanup()

    def test_actual_logged_vosk_transcriptions(self):
        real_samples = [
            "abra o projeto curso no conto",
            "projeto curso no visual estúdio com molde",
            "abra o projeto Curso no VS Code",
            "abra o projeto Curso no Visual Studio Code",
            "abra o projeto curso no visual estudio com",
            "Ângela, abra o meu projeto Curso no VS Code",
            "abra a pasta Curso no VS Code",
            "abra VS Code no projeto Curso",
            "abra Curso no VS Code",
            "abra o projeto Curso",
            "abrir o projeto Curso",
        ]
        for utterance in real_samples:
            with self.subTest(utterance=utterance):
                self.assertEqual(
                    registered_project_alias(utterance, ["Curso"]), "Curso"
                )
                self.assertIn("VS Code", open_registered_project(
                    utterance, self.aliases, launcher=self.runner
                ))
        self.assertEqual(self.runner.call_count, len(real_samples))
        args = [call.args[0] for call in self.runner.call_args_list]
        self.assertTrue(all(item == Project("Curso", self.folder) for item in args))

    def test_ambiguous_or_unrelated_never_open_code(self):
        cases = [
            "abra a pasta Curso", "abra curso", "o projeto Curso usa Visual Studio",
            "como funciona o VS Code?", "abra o VS Code",
            "abra o projeto Curso no Visual Studio",
            "abra o projeto Curso no notebook",
            "abra o projeto Curso e apague arquivos",
            "projeto curso", "curso no conto",
            "abra o meu projeto com isso legítima",
            "abra o projeto Curso no VS Code e execute comandos",
            "abra o projeto Curso no terminal",
        ]
        for message in cases:
            with self.subTest(message=message):
                self.assertIsNone(
                    open_registered_project(message, self.aliases, launcher=self.runner)
                )
        self.runner.assert_not_called()

    def test_unregistered_alias_never_used(self):
        self.assertIsNone(registered_project_alias(
            "abra projeto Desconhecido no VS Code", ["Curso"]
        ))
        self.assertIsNone(
            open_registered_project(
                "abra projeto Desconhecido no VS Code", self.aliases,
                launcher=self.runner
            )
        )
        self.runner.assert_not_called()

    def test_removed_path_fails_closed(self):
        target = self.folder / "pasta removida"
        target.mkdir()
        self.aliases.save("Curso", str(target))
        target.rmdir()
        output = open_registered_project(
            "abra o projeto Curso no VS Code", self.aliases, launcher=self.runner
        )
        self.assertIn("não está disponível", output)
        self.runner.assert_not_called()

    def test_assistant_routes_saved_project_before_generic_project_search(self):
        engine = AssistantEngine(chat=FakeChat())
        engine.folder_registry = self.aliases
        with patch("angela.registered_projects.launch_project",
                   return_value="Enviei o projeto Curso para o VS Code.") as launch:
            with patch("angela.assistant.handle_project_request") as generic:
                result = engine.reply("abra o projeto curso no conto")
        self.assertIn("VS Code", result)
        self.assertEqual(launch.call_count, 1)
        self.assertEqual(launch.call_args.args[0], Project("Curso", self.folder))
        generic.assert_not_called()

    def test_follow_up_project_name_uses_saved_folder(self):
        engine = AssistantEngine(chat=FakeChat())
        engine.folder_registry = self.aliases
        with patch("angela.registered_projects.launch_project",
                   return_value="Enviei o projeto Curso para o VS Code.") as launch:
            prompt = engine.reply("abra o projeto")
            self.assertIn("Qual projeto", prompt)
            result = engine.reply("Curso")
        self.assertIn("VS Code", result)
        launch.assert_called_once_with(Project("Curso", self.folder))

    def test_explorer_alias_route_remains_unchanged(self):
        engine = AssistantEngine(chat=FakeChat())
        engine.folder_registry = self.aliases
        with patch("angela.registered_projects.launch_project") as launch:
            result = engine.reply("abra a pasta Curso")
        self.assertIn("Explorador", result)
        launch.assert_not_called()

    def test_find_custom_install_from_path_code_cmd(self):
        with TemporaryDirectory() as tmp:
            # The real laptop's VS Code uses a custom installation directory.
            root = Path(tmp) / "Microsoft VS Code"
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True)
            (bin_dir / "code.cmd").write_text("@echo off")
            code_exe = root / "Code.exe"
            code_exe.write_bytes(b"fake-test-executable")
            with patch("angela.project_tools.shutil.which",
                       return_value=str(bin_dir / "code.cmd")):
                with patch("angela.project_tools.os.environ.get",
                           return_value="C:\\Nonexistent\\VS Code"):
                    self.assertEqual(find_vscode(), str(code_exe))

    def test_generic_vscode_uses_same_resolved_executable(self):
        from angela.actions import ActionDispatcher
        with patch("angela.project_tools.find_vscode",
                   return_value=r"C:\Apps de programação\Microsoft VS Code\Code.exe"):
            with patch("angela.actions.subprocess.Popen") as popen:
                ActionDispatcher._open_vscode()
        popen.assert_called_once_with(
            [r"C:\Apps de programação\Microsoft VS Code\Code.exe"], shell=False
        )


if __name__ == "__main__":
    unittest.main()
