import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from angela.project_listing import list_request, list_folders, listing_reply
from angela.speech_corrections import correct_transcript
from angela.assistant import AssistantEngine


class TestProjectListing(unittest.TestCase):
    def test_voice_phrases(self):
        self.assertIsNotNone(list_request("Angela, liste quais projetos tenho na pasta Meus Softwares"))
        self.assertIsNotNone(list_request("quais são os meus projetos?"))
        self.assertIsNotNone(list_request("list os projetos que eu tenho na pasta meu software"))
        self.assertIsNotNone(list_request(correct_transcript("este os projetos que eu tenho na pasta meus software")))
        self.assertIsNotNone(list_request(correct_transcript("lixo e quase projetos eu tenho na pasta de meu software")))
        self.assertIsNone(list_request("lixo na pasta de meu software"))
        self.assertIsNone(list_request("Abra o projeto Achei no VS Code"))
        self.assertIsNone(list_request("liste minha pasta privada"))

    def test_allowed_root(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / "Meus Softwares"
            (folder / "Achei").mkdir(parents=True)
            (folder / "docword").mkdir()
            (folder / "anotacoes.txt").write_text("nao listar")
            with patch("angela.project_listing.project_roots", return_value=(folder,)):
                names = list_folders(folder)
            self.assertEqual(names, ["Achei", "docword"])
            self.assertIn("2 pastas", listing_reply(names))

    def test_panel_payload(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            (folder / "Achei").mkdir()
            with patch("angela.assistant.list_request", return_value=folder), patch(
                "angela.assistant.list_folders", return_value=["Achei"]
            ):
                engine = AssistantEngine()
                response = engine.reply("liste projetos")
            self.assertIn("1 pastas", response)
            self.assertEqual(engine.last_panel["items"], ["Achei"])


if __name__ == "__main__":
    unittest.main()
