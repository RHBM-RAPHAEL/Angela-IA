"""Contextual, safe channel navigation after a speech recognition mistake.

Only verified allowlisted channels get direct URLs; arbitrary channel names
require clarification, not guessed destinations or interpretation as lessons.
"""
from __future__ import annotations

import os
import re
import subprocess
import time

from .command_quality import fold
from .windows_apps import rank_matches
from .actions import normalize

ALANZOKA_URL = "https://www.youtube.com/@alanzoka"
_ALIASES = re.compile(
    r"\b(?:alanzoka|alanzoca|alan zoka|alan zoca|alan soca|"
    r"alunos oca|alunosoca|aluno soca|alunos so ca|alã zoka|"
    r"alan oca|alano zoca|alunos soca|alanzoka)\b"
)
_YOUTUBE = re.compile(r"\b(?:youtube|you tube|iutube|iu tube)\b")
_CHANNEL = re.compile(r"\b(?:canal|channel|canau)\b")
_ACTION = re.compile(r"\b(?:abra|abre|abrir|acesse|acessar|mostre|"
                     r"mostrar|entre|entrar|quero ver|quero assistir)\b")


def known_creator(text: str) -> str | None:
    """Only canonicalize an observed phonetic variant in channel context."""
    value = fold(text)
    return "Alanzoka" if _ALIASES.search(value) else None


def youtube_channel_request(text: str) -> bool:
    s = fold(text)
    return len(s) < 240 and bool(_ACTION.search(s) and _YOUTUBE.search(s)
                                 and _CHANNEL.search(s))


def requested_browser(text: str) -> str:
    s = fold(text)
    if re.search(r"\b(?:opera|opera gx|opera ge xis|opera justica)\b", s):
        return "opera"
    if re.search(r"\bchrome\b", s):
        return "chrome"
    if re.search(r"\bedge\b", s):
        return "edge"
    return "default"


class ChannelConversation:
    def __init__(self, *, clock=None):
        self.clock = clock or time.monotonic
        self.pending: tuple[str, float, bool] | None = None

    def handle(self, text: str, *, open_known) -> str | None:
        s = fold(text)
        if youtube_channel_request(text):
            browser = requested_browser(text)
            if known_creator(text) == "Alanzoka":
                self.pending = None
                return open_known(ALANZOKA_URL, browser)
            self.pending = (browser, self.clock() + 70, False)
            return "Qual canal do YouTube você quer abrir?"

        if self.pending is None:
            return None
        browser, expiry, suggested = self.pending
        self.pending = None
        if self.clock() > expiry:
            return "O pedido do canal expirou. Pode pedir novamente."
        if s in {"nao", "cancelar", "cancela", "esquece"}:
            return "Certo, cancelei a abertura do canal."
        if known_creator(text) == "Alanzoka":
            return open_known(ALANZOKA_URL, browser)
        if s in {"aula", "aluno", "alan", "alanzo", "alanz", "alano"}:
            self.pending = (browser, expiry, True)
            return "Você quis dizer o canal Alanzoka?"
        if s in {"sim", "isso", "isso mesmo", "correto", "pode", "pode sim"}:
            if suggested:
                return open_known(ALANZOKA_URL, browser)
            # A short 'sim' alone cannot supply a name.
            self.pending = (browser, expiry, False)
            return "Diga o nome do canal, por favor."
        # Explicit new command should run normally, not open an old website.
        if _ACTION.search(s) or s.startswith(("como ", "o que ", "por que ")):
            return None
        if 0 < len(s) < 65:
            self.pending = (browser, expiry, False)
            return "Não reconheci esse canal. Pode repetir o nome?"
        return None


def open_known_channel(url: str, browser: str, *, windows, startfile=None,
                       popen=None) -> str:
    """Open an allowlisted HTTPS channel in the requested installed browser."""
    if url != ALANZOKA_URL:
        return "Não reconheci esse endereço de canal."
    if browser == "default":
        opener = startfile if startfile is not None else getattr(os, "startfile", None)
        if opener is None:
            return "Só consigo abrir o navegador no Windows."
        try:
            opener(url)
            return "Abri o canal do Alanzoka no YouTube."
        except OSError:
            return "Não consegui abrir o canal no navegador."
    candidates = {
        "opera": "opera gx",
        "chrome": "chrome",
        "edge": "edge",
    }
    target = candidates.get(browser)
    if target is None:
        return "Não reconheci esse navegador."
    apps = windows.catalog.list_apps()
    matching = rank_matches(apps, target)
    if browser == "opera":
        matching = [app for app in apps if app.source == "exe"
                    and "opera" in normalize(app.name + " " + app.target)]
    else:
        matching = [app for app in matching if app.source == "exe"]
    if len(matching) != 1:
        return f"Não encontrei uma instalação única do {browser}."
    runner = popen or subprocess.Popen
    try:
        runner([matching[0].target, url], shell=False)
        return f"Abri o canal do Alanzoka no {matching[0].name}."
    except OSError:
        return f"Não consegui abrir o canal no {browser}."
