"""Determine when Angela should listen for a conversational answer."""
from __future__ import annotations

import re
import unicodedata


def normalized(text: str) -> str:
    value = unicodedata.normalize("NFKD", text.lower())
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", value).strip(" \t\r\n.!?,;")


def wants_to_end(text: str) -> bool:
    """Recognize explicit conversational closure, not a random 'thank you'."""
    value = normalized(text)
    return bool(re.search(
        r"\b(tchau(?: tchau)?|ate (?:logo|mais|a proxima)|encerrar (?:a )?conversa|"
        r"pode parar de (?:me )?ouvir|nao precisa (?:mais )?responder|"
        r"por hoje e so|isso e tudo)\b", value
    ))


def invites_answer(reply: str) -> bool:
    """Conservative question detection; errors and rhetorical statements don't rearm."""
    value = reply.strip()
    if not value or "?" not in value:
        return False
    if value.startswith(("Falha ", "Não foi possível", "Consigo executar comandos locais")):
        return False
    return bool(re.search(r"\?\s*(?:[.!…]*\s*)?$", value))
