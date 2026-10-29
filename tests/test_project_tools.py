"""Testes locais sem abrir programas."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from angela.project_tools import (
    Project, discover_projects, match_project, parse_project_request,
    launch_project, handle_project_request,
)


class ProjectTests(unittest.TestCase):
    def test_identifica_pedidos(self):
        self.assertEqual(parse_project_request("Angela, abra o projeto Valorize no VS Code"), "valorize")
        self.assertEqual(parse_project_request("Abra o VS Code no projeto Zynix"), "zynix")
        self.assertIsNone(parse_project_request("Abra o VS Code"))

    def test_variantes_reais_vosk(self):
        samples = (
            'abro meu projeto achei no verso por favor',
            'abra o projeto achei no visual estúdio cores',
            'abra o projeto achei no visual estúdio com',
        )
        for spoken in samples:
            with self.subTest(spoken=spoken):
                self.assertEqual(parse_project_request(spoken), 'achei')

    def test_pedido_real_do_achei(self):
        self.assertEqual(parse_project_request('abra o meu projeto achei no versículo por favor'), 'achei')
        self.assertEqual(parse_project_request('Angela abra o projeto docword no VS Code'), 'docword')
        self.assertIsNone(parse_project_request('o que e o projeto achei?'))

    def test_pastas_em_meus_softwares(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'Meus Softwares'
            (root / 'Achei').mkdir(parents=True)
            (root / 'docword').mkdir()
            found = discover_projects(roots=[root])
            self.assertEqual({p.name for p in found}, {'Achei', 'docword'})
            self.assertEqual([p.name for p in match_project('achei', found)], ['Achei'])

    def test_descobre_somente_projetos(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            folder = root / "valorize_site"
            folder.mkdir()
            (folder / "package.json").write_text("{}")
            (root / "pasta_comum").mkdir()
            projects = discover_projects(roots=[root])
            self.assertEqual([p.name for p in projects], ["valorize_site"])

    def test_correspondencia_exata_prioritaria(self):
        projects = [Project("zynix", Path("a")), Project("zynix_app", Path("b"))]
        self.assertEqual([p.name for p in match_project("zynix", projects)], ["zynix"])
        self.assertEqual([p.name for p in match_project("zynix app", projects)], ["zynix_app"])

    def test_nao_abre_quando_ambiguo(self):
        with patch("angela.project_tools.discover_projects", return_value=[
            Project("meu_app", Path("a")), Project("meu_app_teste", Path("b"))]):
            launcher = Mock()
            reply = handle_project_request("Abra o projeto meu no VS Code", launcher=launcher)
            self.assertIn("mais de um projeto", reply)
            launcher.assert_not_called()

    def test_lancamento_verifica_erro(self):
        with tempfile.TemporaryDirectory() as td:
            proc = Mock(returncode=1)
            proc.poll.return_value = 1
            launcher = Mock(return_value=proc)
            result = launch_project(Project("teste", Path(td)), executable="Code.exe",
                                    launcher=launcher, sleep=lambda _: None)
            self.assertIn("erro", result)
            self.assertEqual(launcher.call_args.args[0][-1], td)

    def test_lancamento_nao_afirma_janela_confirmada(self):
        with tempfile.TemporaryDirectory() as td:
            proc = Mock(returncode=None)
            proc.poll.return_value = None
            result = launch_project(Project("teste", Path(td)), executable="Code.exe",
                                    launcher=Mock(return_value=proc), sleep=lambda _: None)
            self.assertIn("ainda não identifiquei", result)


if __name__ == "__main__":
    unittest.main()
