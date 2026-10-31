"""User-approved local Windows folder shortcuts, never command execution.

Paths are typed/pasted in UI, verified on save and on open, and only
launched via Explorer. No UNC, URI, shell command, file or relative path.
"""
from __future__ import annotations

import json
import ntpath
import os
from pathlib import Path
import re
import subprocess
import tempfile

from .actions import normalize

FOLDER_DB = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "AngelaAI" / "folder_aliases.json"
MAX_ALIASES = 50
_ALIAS = re.compile(r"^[^\x00-\x1f\\/:*?\"<>|]{2,45}$")
_LOCAL = re.compile(r"^[A-Za-z]:\\[^*?\"<>|\r\n]*$")
_UI_COMMAND = re.compile(
    r"^(?:(?:angela|ei angela)\s+)?"
    r"(?:(?:abra|abre|abrir|mostre|mostrar|configure|configurar|"
    r"cadastre|cadastrar|gerencie|gerenciar|adicione|adicionar)\s+)"
    r"(?:a\s+)?(?:janela|telinha|tela|gerenciador|cadastro|lista)?\s*"
    r"(?:de\s+|da\s+|das\s+)?"
    r"(?:caminhos de pastas|atalhos de pastas|pastas favoritas|"
    r"pastas salvas|cadastrar pastas|gerenciador de pastas)$"
)
_OPEN_ALIAS = re.compile(
    r"^(?:(?:angela|ei angela)\s+)?(?:abra|abre|abrir|"
    r"mostre|mostrar|acesse|acessar)\s+(?:a\s+|o\s+)?"
    r"(?:pasta\s+|diretorio\s+)?(?:de\s+)?(.+)$"
)


def folder_ui_request(message: str) -> bool:
    s = normalize(message).strip(" .,!?")
    s = re.sub(r"^(?:angela|ei angela)[, ]+", "", s)
    if s in {
        "cadastre pastas", "cadastrar pastas", "cadastro de pastas",
        "gerenciar pastas", "gerencie minhas pastas",
        "abrir gerenciador de pastas", "abra gerenciador de pastas",
        "abrir janela de caminhos", "abra janela de caminhos",
        "abrir telinha de pastas", "abra telinha de pastas",
        "adicionar pasta", "adicione uma pasta",
    }:
        return True
    return bool(_UI_COMMAND.fullmatch(s))


def folder_alias_request(message: str) -> str | None:
    s = normalize(message).strip(" .,!?")
    match = _OPEN_ALIAS.fullmatch(s)
    return match.group(1).strip() if match else None


def checked_folder_path(value: str) -> str:
    path = os.path.expandvars(str(value).strip().strip('"').replace("/", "\\"))
    if not _LOCAL.fullmatch(path) or path.startswith("\\\\"):
        raise ValueError("Cole um caminho local absoluto, como D:\\Meus Projetos")
    if any(x in path for x in ("\x00", "\r", "\n")):
        raise ValueError("Caminho inválido")
    resolved = ntpath.normpath(path)
    if not os.path.isdir(resolved):
        raise ValueError("Pasta não encontrada. Confira o caminho.")
    # Prevent a mapped network drive and remote redirection where possible;
    # only visible local drive paths explicitly pasted by user are accepted.
    return resolved


class FolderRegistry:
    def __init__(self, path=None, *, opener=None):
        self.path = Path(path) if path else FOLDER_DB
        self.opener = opener or (
            lambda path: subprocess.Popen(["explorer.exe", path], shell=False)
        )

    def all(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        obj = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(obj, dict) or obj.get("version") != 1:
            raise ValueError("Cadastro de pastas inválido")
        items = obj.get("folders")
        if not isinstance(items, dict):
            raise ValueError("Cadastro de pastas inválido")
        return {
            str(k): str(v) for k, v in list(items.items())[:MAX_ALIASES]
            if isinstance(k, str) and isinstance(v, str)
            and _ALIAS.fullmatch(k)
        }

    def save(self, alias: str, path: str) -> str:
        alias = " ".join(alias.strip().split())
        if not _ALIAS.fullmatch(alias):
            raise ValueError("Escolha um apelido de 2 a 45 caracteres")
        folder = checked_folder_path(path)
        records = self.all()
        records = {
            k: v for k, v in records.items()
            if normalize(k) != normalize(alias)
        }
        if len(records) >= MAX_ALIASES:
            raise ValueError("Limite de 50 pastas atingido")
        records[alias] = folder
        self._commit(records)
        return folder

    def remove(self, alias: str) -> bool:
        records = self.all()
        keys = [key for key in records if normalize(key) == normalize(alias)]
        if not keys:
            return False
        for key in keys:
            del records[key]
        self._commit(records)
        return True

    def resolve(self, spoken: str) -> tuple[str, str] | None:
        alias = normalize(spoken).strip()
        if not alias:
            return None
        for name, path in self.all().items():
            if normalize(name) == alias:
                return name, path
        return None

    def open_alias(self, spoken: str) -> str | None:
        entry = self.resolve(spoken)
        if entry is None:
            return None
        alias, raw_path = entry
        try:
            folder = checked_folder_path(raw_path)
            self.opener(folder)
        except ValueError:
            return f"A pasta {alias} não está mais disponível. Confira o caminho cadastrado."
        except OSError:
            return f"Não consegui abrir a pasta {alias} no Explorador."
        return f"Abri a pasta {alias} no Explorador."

    def _commit(self, items):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", dir=self.path.parent, encoding="utf-8",
                prefix="folders_", suffix=".tmp", delete=False
            ) as file:
                tmp = Path(file.name)
                json.dump({"version": 1, "folders": items}, file,
                          ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        finally:
            if tmp is not None:
                tmp.unlink(missing_ok=True)
