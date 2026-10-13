"""Navegação explícita por unidades e pastas locais do Windows."""
from __future__ import annotations

import ntpath
import os
from pathlib import Path
import re
import subprocess
import sys

from .actions import normalize


class FolderRequestError(ValueError):
    pass


def folder_from_text(message: str) -> str | None:
    """Deriva apenas caminhos explícitos, não adivinha caminhos privados.

    Ex.: 'abra a pasta Imagens no SSD D' -> 'D:\\Imagens'.
    Se o usuário não indicou unidade, só retorna pastas padrão conhecidas.
    """
    text = normalize(message).replace("\\", "/")

    # Caminho absoluto passado por texto: 'D:\Imagens', 'C:/Users/...'.
    absolute = re.search(r"(?<!\w)([a-z]):[\\/]+([^?*\"<>|]*)", message, re.I)
    if absolute:
        letter = absolute.group(1).upper()
        suffix = absolute.group(2).strip().strip(" .!?,;\"'")
        suffix = suffix.replace("/", "\\")
        return ntpath.normpath(f"{letter}:\\{suffix}")

    drive = re.search(
        r"\b(?:ssd|disco|unidade|drive|hd)\s+(?:secundari[oa]\s+)?([a-z])\b",
        text,
    )
    if not drive:
        drive = re.search(r"\bletra\s+([a-z])\b", text)

    folders = list(re.finditer(
        r"\bpasta\s+(?:de\s+)?(?:arquivos\s+)?(?:chamada\s+)?"
        r"([a-z0-9][a-z0-9 _-]{0,70})",
        text,
    ))

    if drive:
        letter = drive.group(1).upper()
        nested = re.findall(
            r"\b(?:na|no|dentro da)\s+pasta\s+([a-z0-9][a-z0-9 _-]{0,70})",
            text,
        )
        if nested:
            chosen = re.split(
                r"\s+(?:no|na|do|da|dentro)\b", nested[-1], 1
            )[0].strip()
            if chosen:
                return f"{letter}:\\{chosen}"

        # Usa a última pasta explicitamente mencionada: "pasta de arquivos
        # no SSD D, na pasta Imagens" resolve para D:\\Imagens.
        for item in reversed(folders):
            name = item.group(1).strip()
            name = re.split(
                r"\s+(?:no|na|do|da|dentro|localizad[oa]|que fica)\b", name, 1
            )[0].strip()
            if name and not name.startswith(("no ", "na ", "do ", "da ")) and name not in {"arquivos", "ssd", "disco", "unidade"}:
                return f"{letter}:\\{name}"
        return f"{letter}:\\"

    # Pastas especiais reconhecidas, sem supor onde o usuário moveu fotos
    # ou transferiu bibliotecas. Shell do Windows resolve Known Folders.
    special = {
        "downloads": "shell:Downloads",
        "documentos": "shell:Personal",
        "area de trabalho": "shell:Desktop",
    }
    if any(k in text for k in ("abra", "abre", "abrir", "mostra", "mostre")):
        for name, shell_path in special.items():
            if name in text:
                return shell_path
    return None


def open_local_folder(target: str) -> str:
    """Abre somente pastas locais, jamais executa o conteúdo de arquivos."""
    if sys.platform != "win32":
        return "A navegação de pastas desta versão funciona somente no Windows."
    if target.startswith("shell:"):
        if target not in {"shell:Downloads", "shell:Personal", "shell:Desktop"}:
            return "Esta pasta especial não está permitida."
        try:
            subprocess.Popen(["explorer.exe", target], shell=False)
            return "Abrindo a pasta solicitada no Explorador."
        except OSError:
            return "Não consegui abrir essa pasta pelo Explorador."

    # Bloqueia caminhos remotos e relativos e sequências especiais.
    if not re.fullmatch(r"[A-Za-z]:\\[^*?\"<>|\r\n]*", target):
        return "Preciso de um caminho local completo, como D:\\Imagens."
    path = ntpath.normpath(target)
    if path.startswith("\\\\"):
        return "Caminhos de rede não são suportados nesta versão."
    if not os.path.isdir(path):
        return f"Não encontrei a pasta {path}. Confira o nome ou a unidade."
    try:
        subprocess.Popen(["explorer.exe", path], shell=False)
        return f"Abrindo a pasta {path}."
    except OSError:
        return "Não consegui iniciar o Explorador de Arquivos."
