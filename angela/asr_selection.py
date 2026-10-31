"""Seleção conservadora entre hipóteses Vosk; sem armazenar áudio ou fala.

A opção alternativa só supera a primeira quando o decodificador oferece
evidência acústica quase equivalente E as palavras descrevem o mesmo pedido.
"""
from __future__ import annotations

import json
import re

from .command_quality import fold

_FACE_CAMERA = re.compile(r"\b(?:camera|webcam|rosto|face)\b")
_FACE_QUESTION = re.compile(
    r"\b(?:reconhece|reconhecer|conhece|conhecer|identifica|identificar)\b"
)
_SAFE_SAME_QUESTION = re.compile(
    r"^(?:(?:voce|tu)\s+)?(?:me\s+)?"
    r"(?:reconhece|reconhecer|conhece|conhecer|identifica|identificar)"
    r"\s+(?:me\s+)?(?:pela?|na|no|atraves da|atraves do)\s+"
    r"(?:camera|webcam|rosto|face)$"
)


def camera_identity_question(text: str) -> bool:
    normalized = fold(text).strip()
    return bool(_FACE_CAMERA.search(normalized) and _SAFE_SAME_QUESTION.fullmatch(normalized))


def choose_recognition(result: str | dict) -> tuple[str, bool]:
    """(recognized_text, used_alt). Funciona com Result() normal e n-best.

    O Vosk fornece confiança RELATIVA, não probabilidade calibrada. Mantemos
    a hipótese principal fora de uma ambiguidade específica e comprovada.
    """
    try:
        data = json.loads(result) if isinstance(result, str) else result
    except (ValueError, TypeError):
        return "", False
    if not isinstance(data, dict):
        return "", False
    alternatives = data.get("alternatives")
    if not isinstance(alternatives, list) or not alternatives:
        return str(data.get("text") or "").strip(), False
    choices = [a for a in alternatives if isinstance(a, dict) and isinstance(a.get("text"), str)]
    if not choices:
        return str(data.get("text") or "").strip(), False
    primary = choices[0]
    text = primary["text"].strip()
    try:
        best_score = float(primary.get("confidence", 0))
    except (TypeError, ValueError):
        return text, False
    if not camera_identity_question(text):
        return text, False
    # Apenas a palavra conhece -> reconhece / identifica dentro do pedido
    # já restrito; jamais transformar outra pergunta ou executar comandos.
    base = fold(text)
    if "reconhece" in base or "reconhecer" in base:
        return text, False
    for option in choices[1:]:
        other = option["text"].strip()
        try:
            diff = best_score - float(option.get("confidence"))
        except (ValueError, TypeError):
            continue
        if (0 <= diff <= 0.10 and camera_identity_question(other)
            and ("reconhece" in fold(other) or "reconhecer" in fold(other))):
            return other, True
    return text, False


def configure_command_recognizer(recognizer) -> None:
    """N-best só para a escuta de comandos, mantendo wake word leve."""
    try:
        recognizer.SetMaxAlternatives(3)
    except (AttributeError, RuntimeError, ValueError):
        pass
