"""Orquestra ações locais do Windows e diálogos de confirmação.

Uma intenção local é resolvida sem mandar nomes de janelas, programas ou
pastas ao serviço de IA. Nenhum comando de shell livre é permitido.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import sys
import time

from .actions import normalize
from .windows_apps import InstalledApp, WindowsAppCatalog, rank_matches
from .windows_folders import folder_from_text, open_local_folder
from .windows_windows import WindowInfo, enumerate_windows, matching_windows, request_close_window

_OPEN = re.compile(
    r"^(?:abra|abre|abrir|inicie|inicia|execute|executa|rode|rodar)\s+(.+)$"
)
_CLOSE = re.compile(
    r"^(?:feche|fecha|fechar|encerre|encerra)\s+(.+)$"
)
_LIST_APPS = (
    "apps instalados", "aplicativos instalados", "programas instalados",
    "quais aplicativos", "quais programas", "liste meus aplicativos",
    "lista meus aplicativos", "mostre meus aplicativos", "meus aplicativos instalados",
)
_LIST_WINDOWS = ("janelas abertas", "quais janelas", "liste as janelas", "mostre as janelas")
_FIND = re.compile(r"^(?:procure|encontre|localize|pesquise)\s+(.+)$")
_GENERIC_PREFIX = re.compile(
    r"^(?:(?:o|a|um|uma|meu|minha)\s+)?"
    r"(?:(?:aplicativo|programa|app|navegador)\s+)?"
    r"(?:(?:o|a|meu|minha)\s+)?"
)


def strip_app_name(name: str) -> str:
    cleaned = normalize(name).strip(" .,!?:;")
    cleaned = _GENERIC_PREFIX.sub("", cleaned)
    return cleaned.strip()


def command_kind(text: str) -> tuple[str, str] | None:
    """Interpreta comandos de sistema; perguntas gerais voltam para o chat."""
    text = normalize(text).strip(" .,!?:;")
    if text.startswith("angela "):
        text = text[7:].lstrip(", ")
    if any(term in text for term in _LIST_APPS):
        return "list_apps", ""
    if any(term in text for term in _LIST_WINDOWS):
        return "list_windows", ""

    # Não confundir pedido de enviar mensagem com pedido de abrir WhatsApp.
    if re.match(r"^(?:mande|manda|envie|envia|escreva|escreve)\s+", text):
        if any(x in text for x in ("mensagem", "whatsapp", "email", "e-mail")):
            return "unsupported_send", ""

    open_match = _OPEN.match(text)
    if open_match:
        raw = open_match.group(1)
        if "pasta" in raw or re.search(r"\b[a-z]:[/\\]", raw):
            return "open_folder", text
        if "ssd " in raw or "disco " in raw or "unidade " in raw:
            return "open_folder", text
        return "open_app", strip_app_name(raw)

    close_match = _CLOSE.match(text)
    if close_match:
        return "close_window", strip_app_name(close_match.group(1))

    found = _FIND.match(text)
    if found and any(w in text for w in ("app", "aplicativo", "programa", "opera", "chrome")):
        return "find_app", strip_app_name(found.group(1))
    return None


@dataclass
class Pending:
    kind: str
    items: list[InstalledApp] | list[WindowInfo]
    expires: float


def _choice_index(message: str, length: int) -> int | None:
    text = normalize(message).strip(" .,!?:;")
    choices = {
        "1": 0, "primeiro": 0, "primeira": 0, "um": 0,
        "2": 1, "segundo": 1, "segunda": 1, "dois": 1,
        "3": 2, "terceiro": 2, "terceira": 2,
        "4": 3, "quarto": 3, "quarta": 3,
        "5": 4, "quinto": 4, "quinta": 4,
    }
    index = choices.get(text)
    if index is None:
        for number, index_ in choices.items():
            if re.fullmatch(r"(?:opcao|numero|a opcao|o numero)\s+" + re.escape(number), text):
                index = index_
                break
    return index if index is not None and index < length else None


class WindowsController:
    def __init__(self, catalog: WindowsAppCatalog | None = None, windows=None,
                 close=None, opener=None, clock=None):
        self.catalog = catalog if catalog is not None else WindowsAppCatalog()
        self.windows = windows if windows is not None else enumerate_windows
        self.close = close if close is not None else request_close_window
        self.open_folder = opener if opener is not None else open_local_folder
        self.clock = clock if clock is not None else time.monotonic
        self.pending: Pending | None = None

    def process(self, text: str) -> str | None:
        if self.pending is not None:
            if self.clock() > self.pending.expires:
                self.pending = None
            else:
                answer = self._continue(text)
                if answer is not None:
                    return answer

        parsed = command_kind(text)
        if parsed is None:
            return None
        action, name = parsed
        if sys.platform != "win32":
            return "Esta função de controle funciona somente no Windows."

        if action == "unsupported_send":
            return ("Ainda não envio mensagens. Posso abrir o WhatsApp, "
                    "mas enviar exige integração, escolha do contato e sua confirmação.")
        if action == "open_folder":
            target = folder_from_text(name)
            if not target:
                return ("Indique a unidade e a pasta, por exemplo: "
                        "'Abra a pasta Imagens no SSD D'.")
            return self.open_folder(target)
        if action == "list_apps":
            apps = self.catalog.list_apps(refresh=True)
            if not apps:
                return "Não encontrei aplicativos no catálogo do Windows."
            names = ", ".join(app.name for app in apps[:18])
            return (f"Encontrei {len(apps)} aplicativos. Alguns são: {names}. "
                    "Diga 'Abra' e o nome do aplicativo.")
        if action == "find_app":
            return self._find_app(name)
        if action == "open_app":
            return self._open_app(name)
        if action == "list_windows":
            windows = self.windows()
            if not windows:
                return "Não encontrei janelas abertas."
            return ("Janelas encontradas: " +
                    "; ".join(w.title for w in windows[:12]) + ".")
        if action == "close_window":
            return self._close_window(name)
        return None

    def _find_app(self, name: str) -> str:
        matches = rank_matches(self.catalog.list_apps(), name)
        if not matches:
            return f"Não encontrei o aplicativo '{name}' no catálogo do Windows."
        return "Encontrei: " + ", ".join(item.name for item in matches[:6]) + "."

    def _open_app(self, name: str) -> str:
        if not name:
            return "Qual aplicativo deseja abrir?"
        # Exigir busca no inventário em vez de executar texto ditado pelo usuário.
        matches = rank_matches(self.catalog.list_apps(), name)
        if not matches:
            return (f"Não encontrei '{name}' nos aplicativos registrados no Windows. "
                    "Posso tentar outro nome do Menu Iniciar.")
        if len(matches) > 1:
            self.pending = Pending("choose_app", matches[:5], self.clock() + 90)
            options = "; ".join(f"{i}. {app.name}" for i, app in enumerate(matches[:5], 1))
            return f"Encontrei mais de uma opção: {options}. Qual deseja abrir?"
        return self._launch(matches[0])

    def _launch(self, app: InstalledApp) -> str:
        try:
            self.catalog.launch(app)
            return f"Solicitei a abertura de {app.name}."
        except (OSError, ValueError) as exc:
            return f"Não consegui abrir {app.name}: {type(exc).__name__}."

    def _close_window(self, name: str) -> str:
        if not name:
            return "Qual janela deseja fechar?"
        hits = matching_windows(self.windows(), name)
        if not hits:
            return f"Não encontrei uma janela aberta correspondente a '{name}'."
        if len(hits) > 1:
            self.pending = Pending("choose_window", hits[:5], self.clock() + 90)
            labels = "; ".join(f"{i}. {item.title}" for i, item in enumerate(hits[:5], 1))
            return f"Encontrei várias janelas: {labels}. Qual delas deseja fechar?"
        return self._ask_close(hits[0])

    def _ask_close(self, window: WindowInfo) -> str:
        if "angela ai" in normalize(window.title):
            return "Por segurança, feche a Ângela pelo botão X da janela."
        self.pending = Pending("confirm_close", [window], self.clock() + 90)
        return (f"Posso solicitar o fechamento de '{window.title}'. "
                "Pode haver trabalho não salvo. Confirmar fechamento? Diga sim ou cancelar.")

    def _continue(self, text: str) -> str | None:
        pending = self.pending
        if pending is None:
            return None
        reply = normalize(text).strip(" .,!?:;")
        if reply in {"nao", "cancela", "cancelar", "pare", "desiste"}:
            self.pending = None
            return "Operação cancelada."
        if pending.kind == "confirm_close":
            if reply in {"sim", "confirmar", "confirmo", "pode", "pode fechar", "fechar"}:
                self.pending = None
                item = pending.items[0]
                if self.close(item):
                    return (f"Solicitei ao Windows que feche '{item.title}'. "
                            "Se houver conteúdo não salvo, o aplicativo poderá pedir confirmação.")
                return "Não consegui enviar o pedido de fechamento; a janela pode ter sido fechada."
            if command_kind(text):
                self.pending = None
                return None
            return "Diga sim para confirmar ou cancelar para manter a janela aberta."

        idx = _choice_index(text, len(pending.items))
        if idx is None:
            names = [item.name if isinstance(item, InstalledApp) else item.title
                     for item in pending.items]
            matches = [i for i, n in enumerate(names) if normalize(n) == reply]
            if len(matches) == 1:
                idx = matches[0]
        if idx is None:
            if command_kind(text):
                self.pending = None
                return None
            return f"Escolha um número de 1 a {len(pending.items)} ou diga cancelar."

        item = pending.items[idx]
        self.pending = None
        if pending.kind == "choose_app":
            return self._launch(item)
        if pending.kind == "choose_window":
            return self._ask_close(item)
        return None
