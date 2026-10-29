"""Interpretação local conservadora: reformula pedidos claros, nunca inventa alvos.

A saída ainda passa pelos mesmos validadores e ferramentas seguras do Windows.
Perguntas explicativas e pedidos sem intenção inequívoca não viram ações.
"""
from __future__ import annotations

import re
from .actions import normalize


def normalize_intent(text: str) -> str:
    original = text.strip()
    if not original or len(original) > 500:
        return original
    s = original
    s = re.sub(r"^(?:(?:oi|olá|ola|ei)\s*[,! ]+)?(?:ângela|angela|anjela)\s*[,! ]*", "", s, flags=re.I).strip()
    s = re.sub(r"^(?:por favor\s*[, ]+)", "", s, flags=re.I).strip()
    if not s:
        return original

    # Nunca converter perguntas sobre COMO fazer em comandos para executar.
    norm = normalize(s)
    if re.match(r"^(?:como|por que|porque|qual a diferenca|o que e|me explique|explique|voce sabe como|sabe como)\b", norm):
        return original
    if re.search(r"\b(?:como|por que)\s+(?:abrir|fechar|executar|alterar)\b", norm):
        return original

    # Verbos claros, com prefixos naturais; captura o complemento sem alterar nomes.
    rules = [
        (r"^(?:voc[eê]\s+)?(?:pode|poderia|consegue)\s+(?:me\s+)?(?:mostrar|mostre)\s+(.+)$", "mostre "),
        (r"^(?:(?:eu\s+)?(?:quero|queria)\s+(?:que\s+voc[eê]\s+)?(?:abra|abrisse|abrir|abre)|gostaria\s+(?:de\s+)?(?:abrir|que\s+voc[eê]\s+abra))\s+(.+)$", "abra "),
        (r"^(?:voc[eê]\s+)?(?:pode|poderia|consegue|conseguiria)\s+(?:por favor\s+)?(?:me\s+)?(?:abrir|abra|abre)\s+(.+)$", "abra "),
        (r"^(?:(?:eu\s+)?(?:quero|queria)\s+(?:que\s+voc[eê]\s+)?(?:feche|fechar)|(?:voc[eê]\s+)?(?:pode|poderia|consegue)\s+(?:me\s+)?(?:fechar|feche))\s+(.+)$", "feche "),
        (r"^(?:me\s+)?(?:mostra|mostrar|mostre)\s+(?:pra\s+mim\s+|para\s+mim\s+)?(.+)$", "mostre "),
        (r"^(?:(?:eu\s+)?(?:quero|queria|gostaria\s+de)\s+)(?:ver|saber)\s+(.+)$", "mostre "),
    ]
    for pattern, verb in rules:
        found = re.match(pattern, s, flags=re.I)
        if found:
            target = found.group(1).strip(" .,!?")
            if not target:
                return original
            # Não transformar pedidos complexos de conversa em ações.
            if re.match(r"^(?:uma\s+explica[cç][aã]o|como\b|se\b|por\s+que\b)", target, flags=re.I):
                return original
            if verb == "mostre " and not re.search(
                    r"\b(?:projetos?|softwares?|aplicativos?|programas?|janelas?|pastas?|diret[oó]rios?)\b",
                    normalize(target)):
                return original
            return verb + target

    # Comandos que já são explícitos, inclusive sem 'são' no meio.
    return s if s != original and re.match(
        r"^(?:abra|abre|abrir|feche|fecha|fechar|inicie|inicia|liste|listar|mostre|quais)\b",
        normalize(s)
    ) else original


def unknown_speech(text: str) -> bool:
    cleaned = normalize(text).strip(" .,!?")
    return cleaned in {"[unk]", "unk", "[unk] [unk]", "???"} or not cleaned
