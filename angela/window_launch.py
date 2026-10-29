"""Confirma visualmente aberturas sem confiar só no PID do processo.

Não força foco nem fecha janelas. Se nenhuma janela nova/visível for
encontrada, informa incerteza em vez de afirmar sucesso.
"""
from __future__ import annotations

import time
from collections.abc import Callable, Iterable

from .command_quality import fold

WINDOW_LABELS = {
    "calculator": ("calculadora", "calculator"),
    "notepad": ("bloco de notas", "notepad"),
    "explorer": ("explorador de arquivos", "file explorer", "explorer"),
    "vscode": ("visual studio code", "vs code"),
}

def is_window_visible_for(
    action: str, windows: Iterable[object]
) -> bool:
    patterns = WINDOW_LABELS.get(action, ())
    return any(
        any(pattern in fold(getattr(item, "title", "")) for pattern in patterns)
        for item in windows
    )

def wait_for_window(
    action: str, *,
    list_windows: Callable[[], Iterable[object]] | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    timeout: float = 2.5,
    interval: float = 0.20,
) -> bool:
    if list_windows is None:
        from .windows_windows import enumerate_windows
        list_windows = enumerate_windows
    if action not in WINDOW_LABELS:
        return False
    cutoff = clock() + max(0, timeout)
    while True:
        try:
            if is_window_visible_for(action, list_windows()):
                return True
        except (OSError, ValueError):
            return False
        now = clock()
        if now >= cutoff:
            return False
        sleep(min(max(interval, 0.01), cutoff - now))
