"""Open explicitly requested local files and Windows Settings pages.

Never executes arbitrary shell commands, scripts, or untrusted executables.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import sys

from .actions import normalize
from .audit_log import record

SETTINGS = {
    "configuracoes": "ms-settings:",
    "configuracao": "ms-settings:",
    "configuracoes do windows": "ms-settings:",
    "configuracoes de tela": "ms-settings:display",
    "configuracoes de video": "ms-settings:display",
    "configuracoes de som": "ms-settings:sound",
    "configuracoes de audio": "ms-settings:sound",
    "configuracoes de bluetooth": "ms-settings:bluetooth",
    "configuracoes de rede": "ms-settings:network",
    "configuracoes de wifi": "ms-settings:network-wifi",
    "configuracoes de wi fi": "ms-settings:network-wifi",
    "configuracoes de bateria": "ms-settings:batterysaver",
    "configuracoes de energia": "ms-settings:powersleep",
    "configuracoes de aplicativos": "ms-settings:appsfeatures",
    "configuracoes de privacidade": "ms-settings:privacy",
    "configuracoes de atualizacao": "ms-settings:windowsupdate",
    "windows update": "ms-settings:windowsupdate",
    "configuracoes de armazenamento": "ms-settings:storagesense",
    "configuracoes de mouse": "ms-settings:mousetouchpad",
    "configuracoes de teclado": "ms-settings:typing",
}
# Only passive document/media types: explicitly exclude executable/script/shortcut types.
SAFE_EXTENSIONS = {
    ".txt", ".md", ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".csv", ".pptx",
    ".ppt", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".mp3", ".mp4",
    ".wav", ".mov", ".avi", ".json", ".xml", ".log", ".yaml", ".yml",
}
PATH_RE = re.compile(r"(?<![a-zA-Z0-9])([a-zA-Z]:[\\/][^\r\n<>|*?\"]+)")
_OPEN_RE = re.compile(r"^(?:abra|abre|abrir|mostre|mostra|exiba)\s+(.*)$")


def resource_request(text: str):
    spoken = normalize(text).strip(" .,!?:;")
    spoken = re.sub(r"^(?:(?:oi|ola|bom dia|boa tarde|boa noite|ei)\s*[,! ]+)*(?:angela|anjela)?[, ]*", "", spoken)
    spoken = re.sub(r"^(?:por favor\s+|voce pode\s+|pode\s+|consegue\s+|pra mim\s+)*", "", spoken)
    spoken = re.sub(r"\s+(?:por favor|pra mim|para mim|se puder)$", "", spoken).strip()
    matched = _OPEN_RE.match(spoken)
    if not matched:
        return None
    target = matched.group(1).strip()
    setting = SETTINGS.get(target)
    if setting:
        return ("settings", setting)
    if target.startswith(("as configuracoes de ", "a configuracao de ")):
        name = re.sub(r"^(?:as configuracoes de |a configuracao de )", "configuracoes de ", target)
        if name in SETTINGS:
            return ("settings", SETTINGS[name])
    if not re.search(r"\b(?:arquivo|documento|planilha|imagem|foto|video|pdf)\b", target) and not PATH_RE.search(text):
        return None
    match = PATH_RE.search(text)
    if match:
        return ("file", match.group(1).strip(" .,!;'\""))
    return None


def open_resource(request, *, opener=None, exists=None, isfile=None, platform=None) -> str:
    kind, target = request
    platform = sys.platform if platform is None else platform
    record("resource_open_attempt", kind=kind, target=target, method="os.startfile")
    if platform != "win32":
        record("resource_open_result", status="failure", reason="not_windows")
        return "Esta função está disponível somente no Windows."
    if kind == "settings":
        if target not in SETTINGS.values():
            record("resource_open_result", status="failure", reason="setting_not_allowed")
            return "Essa configuração não está cadastrada."
        try:
            (opener or os.startfile)(target)
        except OSError as exc:
            record("resource_open_result", status="failure", reason=type(exc).__name__)
            return "Não consegui abrir as Configurações do Windows."
        record("resource_open_result", status="requested", target=target)
        return "Solicitei a abertura dessa configuração do Windows."
    path = Path(target)
    if not path.is_absolute() or path.suffix.lower() not in SAFE_EXTENSIONS:
        record("resource_open_result", status="blocked", reason="unsafe_or_relative_path")
        return "Por segurança, só abro documentos e mídias com caminho completo. Não executo scripts ou programas desconhecidos."
    if not (isfile or os.path.isfile)(str(path)):
        record("resource_open_result", status="failure", reason="file_not_found", target=str(path))
        return f"Não encontrei o arquivo {path}."
    try:
        (opener or os.startfile)(str(path))
    except OSError as exc:
        record("resource_open_result", status="failure", reason=type(exc).__name__)
        return "Não consegui abrir o arquivo no aplicativo padrão."
    record("resource_open_result", status="requested", target=str(path))
    return f"Solicitei a abertura do arquivo {path}."
