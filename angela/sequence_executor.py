"""Sequential, bounded execution of already-supported Windows actions.

Free-form shell commands and destructive operations are never planned.
"""
from __future__ import annotations

import re

from .actions import detect_action, normalize
from .windows_controller import command_kind

MAX_STEPS = 3
_CONNECTOR = re.compile(r"\s+(?:e depois|depois|em seguida|e tambem|e)\s+")


def plan_sequence(text: str) -> list[tuple[str, str]] | None:
    cleaned = normalize(text).strip(" .,!?")
    cleaned = re.sub(r"^(?:angela|anjela)[ ,]*", "", cleaned)
    pieces = [part.strip() for part in _CONNECTOR.split(cleaned)]
    if len(pieces) < 2 or len(pieces) > MAX_STEPS or any(not p for p in pieces):
        return None
    planned = []
    for piece in pieces:
        action = detect_action(piece)
        if action in {"calculator", "notepad", "explorer", "vscode"}:
            planned.append(("action", action))
            continue
        parsed = command_kind(piece)
        if parsed and parsed[0] in {"open_app", "open_folder", "list_windows", "list_apps"}:
            planned.append(("windows", piece))
            continue
        return None
    return planned


def execute_sequence(plan, actions, windows) -> str:
    messages = []
    for index, (kind, value) in enumerate(plan, 1):
        if windows.pending is not None:
            messages.append("Interrompi a sequência porque preciso de uma escolha.")
            break
        try:
            outcome = actions.perform(value) if kind == "action" else windows.process(value)
        except Exception:
            messages.append(f"Etapa {index}: ocorreu uma falha ao executar.")
            break
        messages.append(f"Etapa {index}: {outcome or 'Sem confirmação de execução.'}")
        if windows.pending is not None or not outcome or any(
            term in normalize(outcome) for term in
            ("nao consegui", "nao encontrei", "qual deseja", "qual aplicativo", "indique")
        ):
            messages.append("As etapas seguintes não foram executadas.")
            break
    return " ".join(messages)
