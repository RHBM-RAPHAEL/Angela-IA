"""Descoberta e abertura de aplicativos registrados no Windows.

Não realiza varredura do disco nem executa comandos produzidos pelo modelo.
Fontes: atalhos do Menu Iniciar, App Paths (Registro) e Get-StartApps (UWP).
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from .actions import normalize


@dataclass(frozen=True)
class InstalledApp:
    name: str
    source: str
    target: str


def app_key(name: str) -> str:
    """Normalização também de hífens/pontuação para busca amigável."""
    return " ".join(re.findall(r"[a-z0-9]+", normalize(name)))


def rank_matches(apps: list[InstalledApp], query: str) -> list[InstalledApp]:
    wanted = app_key(query)
    if not wanted or len(wanted) < 2:
        return []
    words = wanted.split()
    candidates = []
    for app in apps:
        key = app_key(app.name)
        if key == wanted:
            rank = 0
        elif key.startswith(wanted + " "):
            rank = 1
        elif wanted in key:
            rank = 2
        elif all(word in key.split() for word in words):
            rank = 3
        else:
            continue
        candidates.append((rank, len(key), app.name.casefold(), app))
    candidates.sort(key=lambda pair: pair[:3])
    return [item[3] for item in candidates[:8]]


class WindowsAppCatalog:
    """Inventário consultado somente quando solicitado; cache por cinco minutos."""

    def __init__(self):
        self._cached: list[InstalledApp] = []
        self._updated = 0.0

    def list_apps(self, refresh: bool = False) -> list[InstalledApp]:
        if sys.platform != "win32":
            return []
        if not refresh and self._updated and time.monotonic() - self._updated < 300:
            return list(self._cached)

        result: list[InstalledApp] = []
        result.extend(self._start_shortcuts())
        result.extend(self._app_paths())
        result.extend(self._start_apps())

        # Evita repetir o mesmo programa em fontes diferentes. Atalho do Menu
        # Iniciar tem preferência por preservar parâmetros oficiais do app.
        unique: dict[str, InstalledApp] = {}
        for app in result:
            key = app_key(app.name)
            if key and key not in unique:
                unique[key] = app
        self._cached = sorted(unique.values(), key=lambda a: app_key(a.name))
        self._updated = time.monotonic()
        return list(self._cached)

    @staticmethod
    def _start_shortcuts() -> list[InstalledApp]:
        roots = []
        appdata = os.environ.get("APPDATA")
        programdata = os.environ.get("PROGRAMDATA")
        if appdata:
            roots.append(Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
        if programdata:
            roots.append(Path(programdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs")

        result = []
        for root in roots:
            try:
                # Limita a quantidade para evitar travar computadores com
                # milhares de atalhos. Não segue links simbólicos de diretório.
                for index, entry in enumerate(root.rglob("*.lnk")):
                    if index >= 2500:
                        break
                    if not entry.is_file():
                        continue
                    name = entry.stem.strip()
                    if name:
                        result.append(InstalledApp(name, "shortcut", str(entry)))
            except (OSError, PermissionError):
                continue
        return result

    @staticmethod
    def _app_paths() -> list[InstalledApp]:
        try:
            import winreg
        except ImportError:
            return []
        entries: list[InstalledApp] = []
        key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(hive, key_path) as key:
                    count = winreg.QueryInfoKey(key)[0]
                    for index in range(min(count, 1500)):
                        try:
                            subname = winreg.EnumKey(key, index)
                            if not subname.lower().endswith(".exe"):
                                continue
                            with winreg.OpenKey(key, subname) as subkey:
                                path, _ = winreg.QueryValueEx(subkey, "")
                            path = os.path.expandvars(str(path)).strip('"')
                            if Path(path).is_file():
                                entries.append(
                                    InstalledApp(Path(subname).stem, "exe", path)
                                )
                        except (OSError, ValueError):
                            continue
            except OSError:
                continue
        return entries

    @staticmethod
    def _start_apps() -> list[InstalledApp]:
        # Get-StartApps devolve identificadores de aplicativos instalados,
        # inclusive alguns apps da Microsoft Store. Sem execução de scripts
        # sugeridos pela IA ou consulta à internet.
        # Evita corromper nomes acentuados no Windows PowerShell 5.1.
        script = (
            "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false); "
            "$OutputEncoding = [Console]::OutputEncoding; "
            "Get-StartApps | Select-Object Name,AppID | ConvertTo-Json "
            "-Compress -Depth 3"
        )
        try:
            done = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=18,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=False,
            )
            if done.returncode != 0 or not done.stdout.strip():
                return []
            parsed = json.loads(done.stdout.lstrip("\ufeff"))
            if isinstance(parsed, dict):
                parsed = [parsed]
            return [
                InstalledApp(str(row["Name"]), "uwp", str(row["AppID"]))
                for row in parsed if row.get("Name") and row.get("AppID")
            ]
        except (OSError, ValueError, subprocess.TimeoutExpired, TypeError):
            return []

    @staticmethod
    def launch(app: InstalledApp) -> None:
        if sys.platform != "win32":
            raise OSError("Disponível somente no Windows.")
        if app.source == "shortcut":
            # O alvo vem do Menu Iniciar, não de texto arbitrário da IA.
            os.startfile(app.target)
        elif app.source == "exe":
            subprocess.Popen([app.target], shell=False)
        elif app.source == "uwp":
            subprocess.Popen(
                ["explorer.exe", "shell:AppsFolder\\" + app.target], shell=False
            )
        else:
            raise ValueError("Fonte do aplicativo não permitida.")
