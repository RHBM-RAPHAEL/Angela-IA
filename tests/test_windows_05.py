"""Testes locais da Ângela 0.5: sem Windows real nem envio de dados."""
import unittest
from unittest.mock import patch

from angela.windows_apps import InstalledApp, app_key, rank_matches
from angela.windows_controller import WindowsController, command_kind
from angela.windows_folders import folder_from_text, open_local_folder
from angela.windows_windows import WindowInfo, matching_windows
from angela.assistant import AssistantEngine


class CatalogFake:
    def __init__(self):
        self.apps = [
            InstalledApp("Opera", "shortcut", r"C:\Menu\Opera.lnk"),
            InstalledApp("Opera GX", "shortcut", r"C:\Menu\Opera GX.lnk"),
            InstalledApp("Google Chrome", "shortcut", r"C:\Menu\Chrome.lnk"),
            InstalledApp("WhatsApp", "uwp", "WhatsApp.AppID"),
        ]
        self.started = []

    def list_apps(self, refresh=False):
        return list(self.apps)

    def launch(self, app):
        self.started.append(app)


class WindowsTest(unittest.TestCase):
    def setUp(self):
        self.catalog = CatalogFake()
        self.windows = [WindowInfo(21, "Calculadora"), WindowInfo(22, "Editor - Bloco de Notas")]
        self.closed = []
        self.opened = []
        self.now = 100.0
        self.controller = WindowsController(
            catalog=self.catalog,
            windows=lambda: list(self.windows),
            close=lambda win: self.closed.append(win) or True,
            opener=lambda path: self.opened.append(path) or "Pasta aberta",
            clock=lambda: self.now,
        )
        self.patcher = patch("angela.windows_controller.sys.platform", "win32")
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_intencao_abrir_app(self):
        self.assertEqual(command_kind("Abra o Opera"), ("open_app", "opera"))
        self.assertEqual(command_kind("Abre o aplicativo WhatsApp"), ("open_app", "whatsapp"))

    def test_intencao_fechar_e_localizar(self):
        self.assertEqual(command_kind("Feche a calculadora"), ("close_window", "calculadora"))
        self.assertEqual(command_kind("Procure o aplicativo Opera"), ("find_app", "opera"))

    def test_envio_nao_automatizado(self):
        self.assertEqual(command_kind("Mande WhatsApp para minha mãe"), ("unsupported_send", ""))
        self.assertIn("não envio mensagens", self.controller.process("Mande WhatsApp para minha mãe"))
        self.assertEqual(self.catalog.started, [])

    def test_catalogo_filtra_por_nome(self):
        self.assertEqual(app_key("Ópera GX!"), "opera gx")
        self.assertEqual(
            [app.name for app in rank_matches(self.catalog.apps, "opera")],
            ["Opera", "Opera GX"],
        )

    def test_abertura_app_unico(self):
        msg = self.controller.process("Abra o Google Chrome")
        self.assertIn("abertura", msg)
        self.assertEqual(self.catalog.started[0].name, "Google Chrome")

    def test_opera_ambigua_pergunta(self):
        msg = self.controller.process("Abra o Opera")
        self.assertIn("mais de uma opção", msg)
        self.assertFalse(self.catalog.started)
        self.assertIn("Opera GX", msg)
        self.assertEqual(self.controller.process("2"), "Solicitei a abertura de Opera GX.")
        self.assertEqual(self.catalog.started[0].name, "Opera GX")

    def test_cancelar_escolha(self):
        self.controller.process("Abra o Opera")
        self.assertEqual(self.controller.process("cancelar"), "Operação cancelada.")
        self.assertEqual(self.catalog.started, [])

    def test_escolha_expira(self):
        self.controller.process("Abra o Opera")
        self.now = 200.0
        answer = self.controller.process("2")
        self.assertIsNone(answer)
        self.assertEqual(self.catalog.started, [])

    def test_app_nao_encontrado(self):
        self.assertIn("Não encontrei", self.controller.process("Abra xyz app que nao existe"))

    def test_listagem_resumida(self):
        self.assertIn("Encontrei 4 aplicativos", self.controller.process("Quais aplicativos instalados?"))

    def test_buscar_aplicativo(self):
        self.assertIn("Opera", self.controller.process("Procure o aplicativo Opera"))

    def test_abrir_pasta_no_ssd(self):
        self.assertEqual(self.controller.process("Abra a pasta Imagens no SSD D"), "Pasta aberta")
        self.assertEqual(self.opened, [r"D:\imagens"])

    def test_nao_adivinha_pasta_sem_unidade(self):
        msg = self.controller.process("Abre a pasta fotos especiais")
        self.assertIn("Indique a unidade", msg)
        self.assertEqual(self.opened, [])

    def test_fecha_so_apos_confirmacao(self):
        msg = self.controller.process("Feche a calculadora")
        self.assertIn("Confirmar fechamento", msg)
        self.assertEqual(self.closed, [])
        self.assertIn("Solicitei ao Windows", self.controller.process("sim"))
        self.assertEqual([item.hwnd for item in self.closed], [21])

    def test_cancelar_fechamento(self):
        self.controller.process("Feche a calculadora")
        self.assertEqual(self.controller.process("não"), "Operação cancelada.")
        self.assertEqual(self.closed, [])

    def test_novo_pedido_substitui_confirmacao(self):
        self.controller.process("Feche a calculadora")
        self.assertIn("abertura", self.controller.process("Abra WhatsApp"))
        self.assertEqual(self.closed, [])
        self.assertIsNone(self.controller.pending)

    def test_pedido_inseguro_nao_execucao(self):
        self.assertIsNone(command_kind("Execute del /f C:\\Users"))
        self.assertEqual(self.catalog.started, [])

    def test_listagem_janelas(self):
        self.assertIn("Calculadora", self.controller.process("Quais janelas abertas?"))


class PureHelpersTest(unittest.TestCase):
    def test_caminho_literal(self):
        self.assertEqual(folder_from_text(r"Abra D:\Imagens"), r"D:\Imagens")

    def test_pasta_falada(self):
        self.assertEqual(folder_from_text("Abra a pasta Imagens no SSD D"), r"D:\imagens")

    def test_unidade(self):
        self.assertEqual(folder_from_text("Abra o SSD D"), "D:\\")

    def test_downloads(self):
        self.assertEqual(folder_from_text("Abra meus downloads"), "shell:Downloads")

    def test_sem_caminho_nao_adivinha(self):
        self.assertIsNone(folder_from_text("Abra uma pasta que não sei onde está"))

    def test_rede_bloqueada(self):
        with patch("angela.windows_folders.sys.platform", "win32"):
            self.assertIn("caminho local", open_local_folder(r"\\servidor\compartilhamento"))

    def test_janelas_similares(self):
        items = [WindowInfo(1, "Opera - Página"), WindowInfo(2, "Chrome - Página")]
        self.assertEqual(matching_windows(items, "Opera")[0].hwnd, 1)

    def test_nao_fecha_outra_coisa_sem_texto(self):
        self.assertEqual(matching_windows([WindowInfo(1, "Calculadora")], ""), [])


class IntegrationTest(unittest.TestCase):
    def test_assistant_usa_controller_sem_groq(self):
        assistant = AssistantEngine()
        assistant.windows = WindowsController(
            catalog=CatalogFake(),
            windows=lambda: [],
            opener=lambda path: f"Abri {path}",
        )
        with patch("angela.windows_controller.sys.platform", "win32"):
            self.assertIn("Abri D:", assistant.reply("Abra a pasta Imagens no SSD D"))

    def test_assistant_preserva_calculadora_antiga(self):
        class DummyActions:
            def perform(self, action):
                return "legacy:" + action
        assistant = AssistantEngine(actions=DummyActions())
        self.assertEqual(assistant.reply("Abra a calculadora"), "legacy:calculator")


if __name__ == "__main__":
    unittest.main()
