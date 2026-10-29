"""Safe, explicit Windows tools. Never execute arbitrary LLM-generated shell text."""
from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .actions import normalize


@dataclass(frozen=True)
class ToolRequest:
    action: str
    target: str = ""


_READ_ONLY_COMMANDS = {
    "hostname": ("hostname",),
    "versao do windows": ("cmd.exe", "/c", "ver"),
    "ipconfig": ("ipconfig.exe",),
    "whoami": ("whoami.exe",),
}


def plan_tool(message: str) -> ToolRequest | None:
    text = normalize(message).strip(" .,!?")
    text = re.sub(r"^(?:angela|anjela)[ ,]*", "", text).strip()
    text = re.sub(r"^(?:por favor|me diga|me fale|pode me dizer|voce sabe)\s+", "", text).strip()
    if text in {"qual o nome do computador", "qual e o nome do computador", "nome do computador", "hostname"}:
        return ToolRequest("read_command", "hostname")
    if text in {"qual a versao do windows", "qual e a versao do windows", "versao do windows"}:
        return ToolRequest("read_command", "versao do windows")
    if text in {"qual meu usuario", "qual e meu usuario", "qual e o meu usuario", "quem sou eu no windows", "whoami"}:
        return ToolRequest("read_command", "whoami")
    if text in {"mostre o ipconfig", "ver ipconfig", "ipconfig", "mostre a configuracao de rede", "qual a configuracao de rede"}:
        return ToolRequest("read_command", "ipconfig")
    if re.match(r"^(?:execute|executar|rode|rodar|abra o terminal|powershell)\b", text):
        return ToolRequest("needs_confirmation", text)
    return None


class WindowsToolExecutor:
    """Runs allowlisted read-only commands; never uses shell=True."""

    def __init__(self, runner=None):
        self.runner = runner or subprocess.run

    def run(self, request: ToolRequest) -> str:
        if request.action == "needs_confirmation":
            return ("Comandos de terminal precisam ser analisados antes de executar. "
                    "Informe a operação e confirme o comando proposto.")
        if request.action != "read_command" or request.target not in _READ_ONLY_COMMANDS:
            return "Ferramenta não autorizada."
        if sys.platform != "win32":
            return "Esta ferramenta está disponível apenas no Windows."
        try:
            result = self.runner(
                list(_READ_ONLY_COMMANDS[request.target]),
                capture_output=True, text=True, timeout=8,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return "Não foi possível executar a consulta ao Windows."
        output = (result.stdout or result.stderr).strip()
        if result.returncode:
            return "A consulta ao Windows retornou um erro."
        return (output[:500] or "Consulta concluída sem conteúdo.")
