"""Small, privacy-conscious dialog memory for recent visual observations.

Retains a short textual caption in RAM for five minutes, no frames or audio.
"""
from __future__ import annotations

from fractions import Fraction
import re
import time

from .command_quality import fold


_EQUATION = re.compile(
    r"(?<![A-Za-z0-9])([+-]?(?:\d+(?:[.,]\d+)?\s*[xX]|[xX]|\d+(?:[.,]\d+)?)"
    r"(?:\s*[+-]\s*(?:\d+(?:[.,]\d+)?\s*[xX]|[xX]|\d+(?:[.,]\d+)?)){0,7}"
    r"\s*=\s*[+-]?(?:\d+(?:[.,]\d+)?\s*[xX]|[xX]|\d+(?:[.,]\d+)?)"
    r"(?:\s*[+-]\s*(?:\d+(?:[.,]\d+)?\s*[xX]|[xX]|\d+(?:[.,]\d+)?)){0,7})(?![A-Za-z0-9])"
)
_MATH_REFER = re.compile(
    r"\b(?:resolv[ae]|resolver|solucion[ae]|solucionar|calcul[ae]|calcular|"
    r"quanto vale o x|qual o valor de x)\b"
)


def asks_to_solve_equation(message: str) -> bool:
    s = fold(message)
    if "como resolver" in s or "me ensine a resolver" in s:
        return False
    return bool(_MATH_REFER.search(s) and re.search(
        r"\b(?:equacao|conta|expressao|valor de x|essa|esta|isso)\b", s
    ))


def asks_about_recent_visual(message: str) -> bool:
    """Anaphoric visual follow-ups, not unrelated new topics."""
    s = fold(message)
    return len(s) <= 170 and bool(re.search(
        r"\b(?:o que (?:voce )?(?:viu|tinha|apareceu|era)|"
        r"me explique (?:isso|essa|aquele|aquilo)|"
        r"o que significa (?:isso|essa|aquilo)|"
        r"qual (?:era|e|foi) (?:a|o) (?:equacao|texto|numero|cor)|"
        r"o que (?:esta|estava) (?:na|no) (?:foto|imagem|caderno))\b",
        s
    ))


def equation_in_text(text: str) -> str | None:
    if not isinstance(text, str):
        return None
    found = _EQUATION.search(text[:1000])
    return " ".join(found.group(1).split()) if found else None


def _expression(expr: str) -> tuple[Fraction, Fraction] | None:
    src = re.sub(r"\s+", "", expr.lower().replace(",", "."))
    if not src or len(src) > 96:
        return None
    if src[0] not in "+-":
        src = "+" + src
    terms = re.findall(r"([+-])(\d*(?:\.\d+)?x|\d+(?:\.\d+)?)", src)
    if not terms or "".join(sign+term for sign, term in terms) != src:
        return None
    coeff, constant = Fraction(0), Fraction(0)
    for sign, term in terms:
        factor = -1 if sign == "-" else 1
        if term.endswith("x"):
            amount = term[:-1]
            coeff += factor * (Fraction(amount) if amount else 1)
        else:
            constant += factor * Fraction(term)
    return coeff, constant


def solve_linear_equation(equation: str) -> str | None:
    """Safe deterministic first-degree solve. No eval/exec."""
    if equation.count("=") != 1 or len(equation) > 160:
        return None
    left, right = equation.split("=")
    lhs, rhs = _expression(left), _expression(right)
    if lhs is None or rhs is None:
        return None
    a, b = lhs[0]-rhs[0], rhs[1]-lhs[1]
    if a == 0:
        return ("A equação tem infinitas soluções." if b == 0
                else "Essa equação não tem solução.")
    answer = b / a
    value = str(answer.numerator) if answer.denominator == 1 else (
        f"{answer.numerator}/{answer.denominator}"
    )
    return f"Na equação {equation}, isolando o x, encontramos x = {value}."


class RecentVisualContext:
    """Single recent caption in volatile memory, for at most 5 minutes."""
    def __init__(self, ttl_seconds: int = 300):
        self.ttl_seconds = max(20, min(int(ttl_seconds), 600))
        self._text = ""
        self._at = 0.0

    def remember(self, caption: str) -> None:
        if not isinstance(caption, str) or not caption.strip():
            return
        self._text = caption.strip()[:850]
        self._at = time.monotonic()

    def current(self) -> str | None:
        if not self._text:
            return None
        if time.monotonic() - self._at > self.ttl_seconds:
            self.forget()
            return None
        return self._text

    def forget(self) -> None:
        self._text = ""
        self._at = 0.0


def visual_location_reply(message: str) -> str | None:
    """Reply to 'where is the equation?' naming a visual source."""
    s = fold(message)
    if s in {"camera", "webcam"}:
        return "camera"
    if s in {"tela", "monitor", "janela ativa"}:
        return "screen"
    if re.fullmatch(
        r"(?:esta|ta|e|fica|olha|olhe|veja)?\s*"
        r"(?:na|pela|na minha|no|pelo)\s*"
        r"(?:camera|webcam|tela|monitor|janela ativa)", s
    ):
        return "camera" if "camera" in s or "webcam" in s else "screen"
    return None
