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
    """Detect a real question even when a statement follows its punctuation.

    Speech-to-text and AI formatting sometimes produce:
    "Posso abrir a câmera? Diga sim ou não." In that case the listener
    should rearm after TTS finishes, never while the speaker is playing.
    """
    value = reply.strip()
    if not value:
        return False
    norm = normalized(value)
    if norm.startswith(("falha ", "nao foi possivel",
                        "consigo executar comandos locais")):
        return False
    if "?" in value:
        return True
    # Some generated questions are missing question marks altogether.
    return bool(re.search(
        r"^(?:posso\s+(?:ativar|ligar|capturar|abrir)|"
        r"voce\s+(?:autoriza|confirma|permite)|"
        r"quer\s+(?:que|apagar|continuar)|"
        r"onde\s+esta|qual\s+(?:imagem|janela|arquivo)|"
        r"pode\s+(?:confirmar|me\s+dizer))\b", norm
    ))
