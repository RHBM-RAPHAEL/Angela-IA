"""Ações locais restritas e explícitas; nunca executar shell gerado por IA."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import unicodedata


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c)).strip()


def detect_action(message: str) -> str | None:
    text = " ".join(normalize(message).replace(",", " ").split())
    if text.startswith("angela "):
        text = text[7:].strip()

    theme_verbs = ("mude", "muda", "coloque", "coloca", "troque", "troca",
                   "altere", "altera", "ative", "ativa", "deixe", "deixa")
    if text.startswith(theme_verbs) and ("tema" in text or "modo" in text):
        if "claro" in text:
            return "theme_light"
        if "escuro" in text:
            return "theme_dark"

    open_verbs = ("abra ", "abre ", "abrir ", "inicie ", "inicia ", "execute ", "executa ")
    if not text.startswith(open_verbs):
        return None
    if "calculadora" in text:
        return "calculator"
    if "bloco de notas" in text or "notepad" in text:
        return "notepad"
    if "explorador" in text or "gerenciador de arquivos" in text:
        return "explorer"
    if "vs code" in text or "visual studio code" in text or "vscode" in text:
        return "vscode"
    return None


class ActionDispatcher:
    """Executa exclusivamente a lista de ações suportadas."""

    def perform(self, action: str) -> str:
        if sys.platform != "win32":
            return "Os comandos de sistema desta versão funcionam somente no Windows."
        try:
            if action == "theme_light":
                self._set_theme(light=True)
                return "Solicitei ao Windows a mudança para o tema claro."
            if action == "theme_dark":
                self._set_theme(light=False)
                return "Solicitei ao Windows a mudança para o tema escuro."
            if action == "calculator":
                subprocess.Popen(["calc.exe"])
                return "Abrindo a calculadora."
            if action == "notepad":
                subprocess.Popen(["notepad.exe"])
                return "Abrindo o Bloco de Notas."
            if action == "explorer":
                subprocess.Popen(["explorer.exe", str(Path.home())])
                return "Abrindo o Explorador de Arquivos."
            if action == "vscode":
                self._open_vscode()
                return "Abrindo o Visual Studio Code."
        except (OSError, ValueError) as exc:
            return f"Não consegui concluir a ação: {exc}"
        return "Este comando ainda não está disponível."

    @staticmethod
    def _open_vscode() -> None:
        candidates = [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Microsoft VS Code" / "Code.exe",
            Path(os.environ.get("PROGRAMFILES", "")) / "Microsoft VS Code" / "Code.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft VS Code" / "Code.exe",
        ]
        executable = next((p for p in candidates if p.is_file()), None)
        if executable is not None:
            subprocess.Popen([str(executable)])
            return
        code = shutil.which("code")
        if code is not None:
            subprocess.Popen([code])
            return
        raise FileNotFoundError("VS Code não encontrado. Verifique se está instalado.")

    @staticmethod
    def _set_theme(light: bool) -> None:
        import ctypes
        import winreg

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        value = 1 if light else 0
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, "AppsUseLightTheme", 0, winreg.REG_DWORD, value)
            winreg.SetValueEx(key, "SystemUsesLightTheme", 0, winreg.REG_DWORD, value)

        # Avisar aplicativos do Windows sobre a alteração.
        result = ctypes.c_size_t(0)
        user32 = ctypes.windll.user32
        user32.SendMessageTimeoutW.argtypes = [
            ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_wchar_p,
            ctypes.c_uint, ctypes.c_uint, ctypes.POINTER(ctypes.c_size_t),
        ]
        user32.SendMessageTimeoutW(
            0xFFFF, 0x001A, 0, "ImmersiveColorSet", 0x0002, 1000,
            ctypes.byref(result),
        )
