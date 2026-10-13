"""Listagem de janelas visíveis e fechamento gentil (WM_CLOSE).

Nunca encerra processos à força, nunca mata processos em segundo plano.
"""
from __future__ import annotations

from dataclasses import dataclass
import sys

from .actions import normalize


@dataclass(frozen=True)
class WindowInfo:
    hwnd: int
    title: str


def matching_windows(windows: list[WindowInfo], query: str) -> list[WindowInfo]:
    target = normalize(query).strip()
    if not target:
        return []
    found = []
    for window in windows:
        name = normalize(window.title)
        if target == name:
            weight = 0
        elif name.startswith(target) or name.endswith(target):
            weight = 1
        elif target in name:
            weight = 2
        else:
            continue
        found.append((weight, len(name), window))
    found.sort(key=lambda row: (row[0], row[1]))
    return [row[2] for row in found[:8]]


def enumerate_windows() -> list[WindowInfo]:
    if sys.platform != "win32":
        return []
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    results: list[WindowInfo] = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL

    def callback(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        count = user32.GetWindowTextLengthW(hwnd)
        if count < 2 or count > 500:
            return True
        buf = ctypes.create_unicode_buffer(count + 1)
        if user32.GetWindowTextW(hwnd, buf, count + 1):
            title = buf.value.strip()
            if title:
                results.append(WindowInfo(int(hwnd), title))
        return True

    cb = callback_type(callback)
    user32.EnumWindows(cb, 0)
    return results


def request_close_window(window: WindowInfo) -> bool:
    """Solicita fechamento normal; app pode pedir confirmação para salvar."""
    if sys.platform != "win32":
        return False
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL
    user32.PostMessageW.argtypes = [
        wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
    ]
    user32.PostMessageW.restype = wintypes.BOOL
    if not user32.IsWindow(window.hwnd):
        return False
    # Proteção adicional: não fecha a própria assistente.
    if "angela ai" in normalize(window.title):
        return False
    return bool(user32.PostMessageW(window.hwnd, 0x0010, 0, 0))
