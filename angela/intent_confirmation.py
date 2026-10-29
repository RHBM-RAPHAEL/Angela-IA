"""Confirmação de nomes de aplicativos confundidos pelo reconhecimento de voz."""
from __future__ import annotations

from dataclasses import dataclass
import re
import time
from .actions import normalize
from .audit_log import record

# Somente variantes ambíguas, nunca corrigir automaticamente.
CANDIDATES = (
    (r"\b(?:virtual studio code|virtual estúdio code|virtual estudio code|aproveite code|viesse code|vence code)\b",
     "Visual Studio Code", "Abra o VS Code"),
    (r"\b(?:esporte|esporte pai no|esporte fai|esporte fai no|esporte fine)\b",
     "Spotify", "Abra o Spotify"),
)


def proposed_app(text: str) -> tuple[str, str] | None:
    normalized = normalize(text)
    if not re.search(r"\b(?:abra|abre|abrir|inicie|inicia|aproveite)\b", normalized):
        return None
    for pattern, label, command in CANDIDATES:
        if re.search(pattern, normalized):
            return label, command
    return None


@dataclass
class AwaitingApp:
    name: str
    command: str
    expiry: float


class IntentConfirmation:
    def __init__(self, clock=None):
        self.clock = clock or time.monotonic
        self.pending: AwaitingApp | None = None

    def propose(self, text: str) -> str | None:
        match = proposed_app(text)
        if not match:
            return None
        name, command = match
        self.pending = AwaitingApp(name, command, self.clock() + 90)
        record("app_intent_confirmation", transcript=text, candidate=name)
        return f"Você quis dizer {name}? Diga sim para abrir ou não para cancelar."

    def resolve(self, text: str) -> tuple[bool, str | None]:
        current = self.pending
        if current is None:
            return False, None
        self.pending = None
        if self.clock() > current.expiry:
            return True, "A confirmação expirou. Pode pedir novamente."
        reply = normalize(text).strip(" .,!?")
        if reply in {"sim", "isso", "exatamente", "correto", "pode", "pode abrir", "confirmo"}:
            return True, current.command
        if reply in {"nao", "não", "cancela", "cancelar", "errado", "na verdade nao"}:
            return True, "Tudo bem, não vou abrir. Qual aplicativo você deseja?"
        # Não interpretar uma frase nova como confirmação.
        return False, None
