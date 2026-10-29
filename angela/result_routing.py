"""Decide quando responder em voz, usar o navegador ou montar uma janela.

Nao usa Qt e nunca interpreta conteudo da IA como codigo executavel.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
import re
from urllib.parse import quote, urlparse, parse_qs

from .command_quality import fold


@dataclass(frozen=True)
class ResultRequest:
    kind: str  # voice, weather, video, browser, text
    subject: str = ""
    url: str = ""


_PREFIX = re.compile(
    r"^(?:(?:oi|ola|ei)\s+)?(?:angela|anjela)?\s*"
    r"(?:(?:por favor|voce pode|pode|poderia|consegue)\s+)*"
    r"(?:(?:me|para mim|pra mim)\s+)?",
)
_SHOW = re.compile(
    r"^(?:(?:me\s+)?(?:mostre|mostrar|mostra|exiba|exibir|apresente|apresentar)|"
    r"(?:eu\s+)?(?:quero|queria)\s+ver|"
    r"(?:me\s+)?(?:mostre\s+para\s+mim))\s+(.+)$",
)
_NOT_VISUAL = re.compile(
    r"\b(?:aplicativos?|programas?|softwares?|projetos?|janelas?|pastas?|"
    r"configuracoes?|arquivos?|documentos?|calculadora|vs\s*code|"
    r"microfone|camera|webcam|tela|monitor)\b"
)
_WEATHER = re.compile(
    r"\b(?:previsao(?:\s+do\s+tempo)?|tempo|clima|"
    r"temperatura(?:\s+de\s+hoje)?)\b"
)
_VIDEO = re.compile(r"\b(?:videos?|clipes?|youtube)\b")
_CLOCK = re.compile(r"^(?:(?:as|a|o|os)\s+)?(?:horas?|horario|hora\s+atual)\b")
_SEARCH = re.compile(r"\b(?:pesquisa|pesquisas|resultados?\s+(?:da\s+)?busca|buscar\s+na\s+internet)\b")
_IMAGES = re.compile(r"\b(?:imagens?|fotos?|fotografias?)\b")
_WEBSITES = re.compile(r"\b(?:site|pagina\s+da\s+internet|pagina\s+web)\b")


def youtube_video_id(text: str) -> str | None:
    """So aceita URLs https YouTube de videos publicos, nunca hosts similares."""
    match = re.search(r"https?://[^\s<>'\"]+", str(text), re.IGNORECASE)
    if not match:
        return None
    raw = match.group(0).rstrip(".,;!?")
    parsed = urlparse(raw)
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port:
        return None
    host = (parsed.hostname or "").lower()
    video_id = None
    if host in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [None])[0]
        elif parsed.path.startswith("/shorts/"):
            video_id = parsed.path.split("/")[2]
    elif host == "youtu.be" and parsed.path.count("/") == 1:
        video_id = parsed.path[1:]
    if video_id and re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        return video_id
    return None


def plan_result_request(text: str) -> ResultRequest | None:
    """Roteador conservador: mostra so quando solicitado explicitamente."""
    if not isinstance(text, str) or len(text) > 450:
        return None
    normalized = fold(text)
    normalized = _PREFIX.sub("", normalized).strip()
    match = _SHOW.match(normalized)
    if not match:
        return None
    subject = match.group(1).strip()
    if not subject or _NOT_VISUAL.search(subject):
        return None
    if _CLOCK.match(subject):
        return ResultRequest("voice", "clock")
    if _WEATHER.search(subject):
        city_match = re.search(
            r"\b(?:em|para|da cidade de|na cidade de)\s+([a-z][a-z0-9 ]{1,65})$",
            subject,
        )
        city = city_match.group(1).strip() if city_match else os.environ.get(
            "ANGELA_WEATHER_CITY", ""
        ).strip()
        return ResultRequest("weather", city[:65])
    if _VIDEO.search(subject):
        video_id = youtube_video_id(text)
        if video_id:
            return ResultRequest(
                "video", subject[:150],
                "https://www.youtube-nocookie.com/embed/" + video_id,
            )
        search = re.sub(
            r"^(?:o|a|um|uma|os|as)\s+", "", subject
        ).strip()
        search = re.sub(r"\b(?:video|videos|clipe|clipes|do youtube|no youtube)\b", " ", search)
        search = " ".join(search.split()) or subject
        return ResultRequest(
            "video", search[:150],
            "https://www.youtube.com/results?search_query=" + quote(search[:150]),
        )
    if _IMAGES.search(subject):
        query = re.sub(
            r"^(?:(?:as|uma|algumas|a)\s+)?(?:imagens?|fotos?|fotografias?)\s*(?:de|do|da|sobre)?\s*",
            "", subject,
        ).strip()
        return ResultRequest("browser_images", query[:160] or subject[:160])
    if _WEBSITES.search(subject):
        query = re.sub(
            r"^(?:(?:o|um|a|uma)\s+)?(?:site|pagina da internet|pagina web)\s*(?:de|do|da)?\s*",
            "", subject,
        ).strip()
        return ResultRequest("browser", query[:160] or subject[:160])
    if _SEARCH.search(subject):
        query = re.sub(
            r"^(?:a|as|o|os)\s+(?:pesquisas?|resultados?\s+(?:da\s+)?busca)\s*(?:sobre|de|do|da)?\s*",
            "", subject,
        ).strip()
        return ResultRequest("browser", query[:160] or subject[:160])
    return ResultRequest("text", subject[:180])
