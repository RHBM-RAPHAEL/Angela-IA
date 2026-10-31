"""Voice commands for an explicitly activated, local live camera preview.

The activation command itself authorizes displaying the local preview.
It never authorizes sharing imagery with a remote vision model.
"""
from __future__ import annotations

import re

from .actions import normalize


def camera_mode_command(message: str) -> str | None:
    if not isinstance(message, str) or not 0 < len(message) <= 200:
        return None
    s = " ".join(normalize(message).split())
    s = re.sub(r"^(?:angela|anjela|ei angela)[\s,;:!]+", "", s).strip(" ?!.,")
    if re.fullmatch(
        r"(?:ative|ativar|ativa|ligue|ligar|liga|inicie|iniciar|"
        r"abra|abrir|habilite|habilitar|"
        r"quero ativar|pode ativar)\s+(?:a\s+)?"
        r"(?:visao computacional|visao pela camera|camera ao vivo)", s
    ):
        return "open"
    if re.fullmatch(
        r"(?:feche|fechar|fecha|desative|desativar|desliga|desligue|"
        r"pare|parar|encerre|encerrar|desabilite)\s+"
        r"(?:a\s+|minha\s+)?(?:camera|webcam|visao computacional|"
        r"visao pela camera|camera ao vivo|janela da camera)", s
    ):
        return "close"
    return None


def contextual_camera_question(message: str) -> bool:
    """When preview is open, detect visual questions without word 'câmera'.

    Purely informational questions (e.g. how a webcam works) must not
    trigger image capture or remote model requests.
    """
    if not isinstance(message, str) or not 0 < len(message) <= 350:
        return False
    s = " ".join(normalize(message).split())
    if re.search(r"\b(?:como funciona|como configurar|como instalar|"
                 r"como comprar|tutorial|qual a melhor)\b", s):
        return False
    patterns = (
        r"\b(?:o que|que)\s+(?:voce\s+)?(?:ve|esta vendo|enxerga|percebe)\b",
        r"\b(?:o que|qual)\s+(?:e|representa|significa)\s+"
        r"(?:esse|este|essa|esta|o|a)\s+"
        r"(?:desenho|objeto|imagem|figura|simbolo|coisa)\b",
        r"\b(?:o que|qual)\s+(?:e|representa)\s+(?:isso|isto|aquilo)\b",
        r"\b(?:olhe|olha|veja|analise|analisa|examine|examina|"
        r"descreva|descreve)\s+(?:isso|isto|aqui|este|esse|"
        r"essa|o que|meu|minha|a|o)\b",
        r"\b(?:o que|qual)\s+(?:eu\s+)?(?:estou segurando|"
        r"esta escrito|tem aqui|aparece aqui)\b",
        r"\b(?:leia|ler|resolva|resolve|resolver|"
        r"calcule|calcula|calcular)\s+(?:essa|esta|a|o)\s+"
        r"(?:equacao|conta|expressao|texto|numero)\b",
        r"\b(?:qual|quais)\s+(?:e|sao)\s+(?:o|a|os|as)\s+"
        r"(?:objeto|objetos|cor|cores)\s+(?:aqui|nessa|nesta|desse|dessa)?\b",
        r"\b(?:o que tem|o que esta)\s+(?:aqui|na minha mao|"
        r"nesse papel|neste caderno)\b",
    )
    return any(re.search(pattern, s) for pattern in patterns)
