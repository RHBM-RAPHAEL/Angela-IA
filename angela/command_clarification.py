"""Esclarece alvos ausentes sem adivinhar nem executar ações diretamente."""
from __future__ import annotations

from dataclasses import dataclass
import re
import time
from .actions import normalize
from .audit_log import record


@dataclass
class PendingQuestion:
    kind: str
    expires: float


class CommandClarification:
    def __init__(self, clock=None):
        self.clock = clock or time.monotonic
        self.pending: PendingQuestion | None = None

    def ask_if_needed(self, text: str) -> str | None:
        clean = normalize(text).strip(" .,!?")
        queries = [
            (r"^(?:abra|abre|abrir)\s+(?:(?:o|meu)\s+)?(?:projeto|repositorio)$",
             "project", "Qual projeto deseja abrir no VS Code?"),
            (r"^(?:abra|abre|abrir)\s*(?:(?:um|o)\s+)?(?:aplicativo|programa|app)?$",
             "app", "Qual aplicativo deseja abrir?"),
            (r"^(?:feche|fecha|fechar|encerre|encerra)\s*(?:a\s+janela|o\s+programa)?$",
             "window", "Qual janela deseja fechar?"),
        ]
        for pattern, kind, reply in queries:
            if re.fullmatch(pattern, clean):
                self.pending = PendingQuestion(kind, self.clock() + 70)
                record("command_clarification_requested", kind=kind)
                return reply
        return None

    def resolve(self, answer: str) -> tuple[bool, str | None]:
        pending = self.pending
        if pending is None:
            return False, None
        self.pending = None
        if self.clock() > pending.expires:
            return True, "Essa pergunta expirou. Repita o pedido, por favor."
        target = answer.strip(" .,!?")
        clean = normalize(target)
        if clean in {"nao", "cancelar", "cancela", "deixa pra la", "esquece"}:
            record("command_clarification_cancelled", kind=pending.kind)
            return True, "Certo, cancelei esse pedido."
        if re.match(r"^(?:abra|abre|feche|fecha|liste|mostre|mude|altere|apague|delete|execute|rode|envie|mande)\b", clean):
            return False, None
        if not target or len(target) > 65 or len(target.split()) > 7:
            return False, None
        if re.search(r"[/\\:;<>|$]", target) or re.search(r"\b(?:apague|delete|senha|token|powershell|terminal|execute|comando)\b", clean):
            return False, None
        if clean in {"sim", "isso", "nao sei", "tanto faz", "qualquer um"}:
            return True, "Preciso de um nome específico. Repita o pedido com o nome."
        prefix = {"project": "abra o projeto ", "app": "abra ", "window": "feche "}[pending.kind]
        rebuilt = prefix + target
        record("command_clarification_resolved", kind=pending.kind, selected=target)
        return True, rebuilt
