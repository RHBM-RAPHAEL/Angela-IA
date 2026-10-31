"""Intenções locais conservadoras e qualidade das respostas por voz.

Funções puras, portáveis: não executam aplicativos nem acessam serviços remotos.
Qualquer destino ambíguo exige esclarecimento em vez de adivinhação.
"""
from __future__ import annotations

from datetime import datetime
import re
import unicodedata

def fold(text: str) -> str:
    base = unicodedata.normalize("NFKD", str(text).casefold())
    base = "".join(c for c in base if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", base).split())

def correct_known_speech(text: str) -> str:
    """Ajusta erros Vosk apenas em contextos onde a intenção é explícita."""
    spoken = text.strip()
    # Fora de 'meus projetos', 'Alice' é o nome de alguém e deve ser preservado.
    spoken = re.sub(
        r"^(?:(?:alice|alise|alisse|este|lixe|liste|list)\s+)"
        r"(?=(?:os\s+)?meus\s+projetos\b)",
        "liste ", spoken, flags=re.IGNORECASE
    )
    return spoken

def normalize_request(text: str) -> str:
    """Reformula pedidos locais inequívocos. Outros textos seguem intactos."""
    original = text.strip()
    if not original or len(original) > 400:
        return original
    spoken = correct_known_speech(original)
    spoken = re.sub(
        r"^(?:(?:oi|ei|ola|olá)[,! ]+)?(?:ângela|angela|anjela)[,! ]*",
        "", spoken, flags=re.IGNORECASE
    ).strip()
    spoken = re.sub(r"^(?:por favor)[,! ]+", "", spoken, flags=re.IGNORECASE)
    if not spoken:
        return original
    normalized = fold(spoken)
    if re.match(
        r"^(?:como|por que|porque|voce sabe como|qual a diferenca|"
        r"o que e|me explique|explique)\b",
        normalized
    ):
        return original
    if re.search(r"\b(?:como|por que)\s+(?:abrir|fechar|executar)\b", normalized):
        return original

    # Só se infere "abra" para nomes de apps conhecidos, não para texto livre.
    if re.fullmatch(
        r"(?:a |o )?(?:calculadora|calc)(?: de novo| para mim| pra mim)?"
        r"(?: por favor)?", normalized
    ):
        return "abra a calculadora"

    # Ex.: "poderia abrir a calculadora?" / "queria que você abrisse o VS Code"
    patterns = (
        (r"^(?:voce\s+)?(?:pode|poderia|consegue|conseguiria)\s+"
         r"(?:por favor\s+)?(?:me\s+)?(?:abrir|abra|abre)\s+(.+)$", "abra "),
        (r"^(?:(?:eu\s+)?(?:quero|queria)\s+(?:que\s+voce\s+)?"
         r"(?:abrir|abra|abrisse|abre)|gostaria\s+de\s+abrir)\s+(.+)$", "abra "),
        (r"^(?:voce\s+)?(?:pode|poderia|consegue)\s+"
         r"(?:me\s+)?(?:fechar|feche)\s+(.+)$", "feche "),
        (r"^(?:(?:voce\s+)?(?:pode|poderia|consegue)\s+"
         r"(?:me\s+)?(?:mostrar|mostre)|(?:me\s+)?(?:mostra|mostre)|"
         r"(?:eu\s+)?(?:quero|queria)\s+ver)\s+(.+)$", "mostre "),
    )
    for pattern, prefix in patterns:
        match = re.fullmatch(pattern, normalized)
        if not match:
            continue
        target = match.group(1).strip()
        if prefix == "mostre " and not re.search(
            r"\b(?:projetos?|softwares?|aplicativos?|programas?|janelas?|pastas?)\b",
            target
        ):
            return original
        if not target or re.search(
            r"^(?:como|por que|um exemplo|uma explicacao|se)\b", target
        ):
            return original
        return prefix + target
    return spoken if spoken != original and re.match(
        r"^(?:abra|abre|feche|fecha|liste|mostre|quais)\b", fold(spoken)
    ) else (spoken if spoken != original and fold(spoken).startswith("liste ") else original)

def clock_request(text: str) -> bool:
    s = fold(text)
    if re.match(r"^(?:como|por que|porque)\b", s):
        return False
    if re.search(r"\b(?:que|qual)\s+horas?\s+(?:sao|e|agora)\b", s):
        return True
    if re.search(r"\b(?:horas?|horario)\s+(?:agora|atual|neste momento)\b", s):
        return True
    return bool(re.search(
        r"\b(?:diga|fala|fale|falha|diz|informe|adivinhe|saber|ver)\b"
        r"(?:\s+(?:me|as|a|que|qual|sao|o|atual|de))*"
        r"\s+(?:horas?|horario)\b", s
    ))

def local_clock_reply(now: datetime | None = None) -> str:
    now = now or datetime.now()
    return f"Agora são {now.hour:02d}:{now.minute:02d}."

def browser_intent(text: str) -> tuple[str, str] | None:
    """(site, browser) com browser: default/opera/chrome/edge/ask. Só lista fechada."""
    s = fold(text)
    if re.match(r"^(?:como|por que|porque|o que)\b", s):
        return None
    if not re.search(r"\b(?:abra|abre|abrir|acesse|acessar|entre|entrar)\b", s):
        return None
    found = [name for name in ("youtube", "google", "github", "gmail") if re.search(r"\b"+name+r"\b", s)]
    if len(found) != 1:
        return None
    # 'não Opera' pode ser Vosk para 'no Opera'. Não escolher silenciosamente.
    if re.search(r"\b(?:nao|sem)\s+(?:o\s+)?(?:opera|chrome|edge)\b", s):
        return found[0], "ask"
    if "opera" in s:
        return found[0], "opera"
    if re.search(r"\bchrome\b", s):
        return found[0], "chrome"
    if re.search(r"\bedge\b", s):
        return found[0], "edge"
    return found[0], "default"

def execution_feedback_eligible(reply: str, attempted_action: bool) -> bool:
    """Feedback apenas para tentativas reais, nunca para falta de aplicativo."""
    if not attempted_action:
        return False
    s = fold(reply)
    failures = (
        "nao encontrei", "nao consegui", "nao foi possivel",
        "preciso de um nome", "qual aplicativo", "qual janela",
        "confirmar fechamento", "encontrei varias", "ainda nao",
        "erro", "indique a unidade", "especifique"
    )
    return not any(fail in s for fail in failures)

def speech_summary(reply: str, limit: int = 240) -> str:
    """Fala somente o essencial, sem encaminhar a pessoa para o painel.

    A resposta original ainda pode ser lida na interface. Aqui removemos
    introducoes vazias e preferimos frases completas em vez de truncamento
    abrupto. A IA permanece disponivel para perguntas de acompanhamento.
    """
    compact = re.sub(r"(?m)^\s*[-*#>]+\s*", "", str(reply))
    compact = re.sub(r"\*\*(.*?)\*\*|__(.*?)__", lambda m: m.group(1) or m.group(2), compact)
    compact = re.sub(r"`([^`]+)`", r"\1", compact)
    compact = re.sub(r"https?://\S+", "link", compact)
    compact = re.sub(
        r"(?i)\b(?:a resposta completa est[aá] no painel|"
        r"o restante est[aá] no chat|leia o restante no chat|"
        r"os detalhes est[aã]o no chat)\s*[.!?]?", "", compact
    )
    compact = re.sub(
        r"(?i)^(?:ol[aá][!,]?\s*)?(?:aqui est[aá] (?:a descri[cç][aã]o|"
        r"o que (?:eu )?vejo)(?: (?:dessa|desta|na) (?:imagem|foto|webcam))?"
        r"\s*[:.!]?\s*)", "", compact.strip()
    )
    compact = " ".join(compact.split()).strip(" -;:")
    if not compact:
        return "Pode repetir sua pergunta?"
    maximum = max(70, min(int(limit), 600))
    if len(compact) <= maximum:
        return compact
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-ÖØ-Ý0-9])", compact)
    chosen = ""
    for sentence in sentences:
        candidate = (chosen + " " + sentence).strip()
        if len(candidate) > maximum:
            break
        chosen = candidate
        if len(chosen) >= maximum * 0.57:
            break
    if chosen and len(chosen) >= 32:
        return chosen
    cut = compact[:maximum].rsplit(" ", 1)[0].rstrip(" ,;:-")
    return cut if cut.endswith((".", "!", "?")) else cut + "."
