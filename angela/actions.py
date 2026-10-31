"""Ações locais restritas e explícitas; nunca executar shell gerado por IA."""
from __future__ import annotations

import os
import re
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
    text = re.sub(r'^(?:oi |ei |ola )?(?:angela |anjela )', '', text).strip()
    text = re.sub(r'^(?:por favor |voce pode |pode |pra mim |para mim )+', '', text)
    text = re.sub(r'^(?:voce consegue |consegue )', '', text)

    theme_verbs = ("mude", "muda", "coloque", "coloca", "troque", "troca",
                   "altere", "altera", "ative", "ativa", "deixe", "deixa")
    if text.startswith(theme_verbs) and ("tema" in text or "modo" in text):
        if "claro" in text:
            return "theme_light"
        if "escuro" in text:
            return "theme_dark"

    open_verbs = ("abra ", "abre ", "abrir ", "inicie ", "inicia ", "execute ", "executa ", "abrindo ", "abrir o ")
    if not text.startswith(open_verbs):
        if re.fullmatch(r'(?:a |o )?(?:calculadora|calc|calculador)(?: para mim| por favor)?', text):
            return 'calculator'
        return None
    if "calculadora" in text or re.search(r'\bcalc\b', text):
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
                return self._check_window("calculator", "Calculadora")
            if action == "notepad":
                subprocess.Popen(["notepad.exe"])
                return self._check_window("notepad", "Bloco de Notas")
            if action == "explorer":
                subprocess.Popen(["explorer.exe", str(Path.home())])
                return self._check_window("explorer", "Explorador de Arquivos")
            if action == "vscode":
                self._open_vscode()
                return self._check_window("vscode", "Visual Studio Code")
        except (OSError, ValueError) as exc:
            return f"Não consegui concluir a ação: {exc}"
        return "Este comando ainda não está disponível."

    @staticmethod
    def _check_window(action: str, label: str) -> str:
        from .window_launch import wait_for_window
        if wait_for_window(action, timeout=2.5):
            return f'Confirmei que {label} está aberto.'
        return (f'Solicitei a abertura de {label}, mas ainda não consegui '
                'confirmar a janela. Verifique se apareceu na área de trabalho.')

    @staticmethod
    def _open_vscode() -> None:
        from .project_tools import find_vscode
        executable = find_vscode()
        if executable is None:
            raise FileNotFoundError("VS Code não encontrado. Verifique se está instalado.")
        subprocess.Popen([executable], shell=False)

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
