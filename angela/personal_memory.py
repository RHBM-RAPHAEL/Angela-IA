"""Explicit opt-in persistent local memory for Angela AI.

Never learn automatically from chat/audio/history. Entries are encrypted using
Windows CurrentUser DPAPI and are not published to Groq or included in logs.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import tempfile
from datetime import datetime, timezone

from .actions import normalize

DEFAULT_MEMORY_PATH = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "AngelaAI" / "personal_memory.dat"
MAX_ITEMS = 36
MAX_FACT = 260
STOPWORDS = set(("eu meu minha meus minhas o a os as de do da dos das e em na no "
                 "que qual quais quem como um uma uns umas voce sabe sobre mim para "
                 "com voce lembra lembrava me por tenho tem sou esta estou foi "
                 "era lembro quanto onde fica se").split())
SECRET_PATTERN = re.compile(
    r"\b(?:senha|password|api.?key|chave de api|token|codigo de verificacao|"
    r"c[oó]digo de acesso|cpf|rg|cvv|cart[aã]o de cr[eé]dito|"
    r"chave privada|private key|seed phrase|frase de recupera[cç][aã]o)\b",
    re.IGNORECASE,
)
SAVE = re.compile(
    r"^(?:(?:angela|ei angela)[, ]+)?(?:salv[ea]|guardar?|guarde|"
    r"anote|memorize|lembre) (?:isso )?(?:na |em sua |em minha )?"
    r"(?:memoria|memoria pessoal)(?:\s+(?:que|de que|:)\s*(.*))?$"
)
SAVE_ALT = re.compile(
    r"^(?:(?:angela|ei angela)[, ]+)?(?:salv[ea]|guarde|anote|lembre)"
    r"\s+(?:na memoria\s+)?que\s+(.+)$"
)
FORGET = re.compile(
    r"^(?:(?:angela|ei angela)[, ]+)?(?:apague|apagar|esqueca|"
    r"esquecer|remova|remover|delete|exclua)\s+"
    r"(?:(?:da|de sua|na|a)\s+)?(?:memoria|lembranca)"
    r"(?:\s+(?:sobre|de|do|da)\s+(.+))?$"
)
RECALL = re.compile(
    r"^(?:o que (?:voce )?(?:lembra|sabe|guardou) (?:de|sobre) mim|"
    r"mostre (?:minhas|as) memorias|liste (?:as )?memorias|"
    r"o que (?:esta|tem) (?:salvo|guardado) na memoria)$"
)


def memory_request(message: str) -> tuple[str, str] | None:
    s = " ".join(normalize(message).strip(" .,!?").split())
    if len(s) > 500:
        return None
    match = SAVE.fullmatch(s)
    if match:
        # Keep original accents in saved fact, not normalized transcription.
        candidate = re.sub(
            r"^(?:(?:ângela|angela|ei ângela|ei angela)[, ]+)?"
            r"(?:salve|salva|guardar?|guarde|anote|memorize|lembre)\s+"
            r"(?:isso\s+)?(?:na |em sua |em minha )?"
            r"(?:memória|memoria|memória pessoal|memoria pessoal)"
            r"(?:\s+(?:que|de que|:)\s*)?", "",
            message.strip(), flags=re.IGNORECASE
        ).strip(" .,!?")
        return "save", candidate if match.group(1) else ""
    alt = SAVE_ALT.fullmatch(s)
    if alt:
        return "save", message.strip()[len(message)-len(alt.group(1)):].strip()
    match = FORGET.fullmatch(s)
    if match:
        return "forget", match.group(1) or ""
    if RECALL.fullmatch(s):
        return "list", ""
    return None


def _keywords(text: str) -> set[str]:
    s = normalize(text)
    words = {
        token for token in re.findall(r"[a-z0-9]+", s)
        if len(token) >= 3 and token not in STOPWORDS
    }
    # "Me chamo Rafael" deve responder "Qual é meu nome?" sem IA remota.
    if re.search(r"\b(?:me chamo|meu nome e|qual (?:e )?(?:o )?meu nome)\b", s):
        words.add("nome")
    return words


def _dpapi(data: bytes, *, decrypt: bool) -> bytes:
    # Reuse the tested Windows DPAPI primitive; no fallback to plain JSON.
    from .face_identity import _dpapi as protect
    return protect(data, decrypt=decrypt)


class PersonalMemory:
    def __init__(self, path=None, *, protect=None, unprotect=None):
        self.path = Path(path) if path is not None else DEFAULT_MEMORY_PATH
        self.protect = protect or (lambda b: _dpapi(b, decrypt=False))
        self.unprotect = unprotect or (lambda b: _dpapi(b, decrypt=True))

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        raw = self.unprotect(self.path.read_bytes())
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("items"), list):
            raise ValueError("Formato de memória inválido")
        return [
            item for item in data["items"][:MAX_ITEMS] if isinstance(item, dict)
            and isinstance(item.get("fact"), str)
        ]

    def _commit(self, items: list[dict]):
        payload = json.dumps(
            {"version": 1, "items": items[-MAX_ITEMS:]},
            ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        if len(payload) > 16000:
            raise ValueError("Limite de memória excedido")
        ciphertext = self.protect(payload)
        if not isinstance(ciphertext, bytes) or not ciphertext:
            raise ValueError("Não foi possível proteger a memória")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=self.path.parent,
                prefix="personal_", suffix=".tmp", delete=False
            ) as file:
                tmp = Path(file.name)
                file.write(ciphertext)
            os.replace(tmp, self.path)
        finally:
            if tmp is not None:
                tmp.unlink(missing_ok=True)

    def add(self, fact: str):
        value = " ".join(str(fact).split()).strip(" .")
        if not 4 <= len(value) <= MAX_FACT:
            raise ValueError("Diga uma informação com até 260 caracteres")
        if SECRET_PATTERN.search(value):
            raise ValueError("Não salvo senhas, tokens ou documentos sensíveis na memória")
        records = self._load()
        # No exact duplicates or unbounded growth.
        key = normalize(value)
        records = [row for row in records if normalize(row["fact"]) != key]
        records.append({"fact": value,
                        "saved_at": datetime.now(timezone.utc).isoformat()})
        self._commit(records[-MAX_ITEMS:])

    def all(self) -> list[str]:
        return [item["fact"] for item in self._load()]

    def relevant(self, question: str, *, max_results=3) -> list[str]:
        search = _keywords(question)
        if not search:
            return []
        scores = []
        for i, entry in enumerate(self.all()):
            match = len(search & _keywords(entry))
            if match:
                scores.append((match, i, entry))
        return [entry for _, _, entry in sorted(scores, reverse=True)[:max_results]]

    def forget(self, subject: str) -> int:
        wanted = _keywords(subject)
        if not wanted:
            return 0
        items = self._load()
        retained = [item for item in items if not (wanted & _keywords(item["fact"]))]
        deleted = len(items) - len(retained)
        if deleted:
            self._commit(retained)
        return deleted

    def clear(self):
        if self.path.exists():
            self.path.unlink()
