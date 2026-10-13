"""Conversa pela API Groq (opcional); não permite executar ações por IA."""
from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv

load_dotenv()
API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-oss-20b"
RETIRED_MODELS = frozenset({
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
})
SYSTEM_PROMPT = (
    "Você é Ângela, uma assistente pessoal feminina de Windows. "
    "Responda em português brasileiro, com clareza, de forma curta e cordial. "
    "Você NÃO controla o computador por esta interface de chat; "
    "as ações locais são implementadas separadamente. "
    "Nunca afirme que abriu programas, alterou configurações ou observou a tela "
    "sem confirmação real. Não invente acesso à câmera ou a arquivos. "
    "Não peça senhas, tokens ou chaves."
)


def select_model(model: str | None) -> str:
    """Migra o modelo desativado em 2026, inclusive em .env antigos."""
    requested = (model or "").strip()
    if not requested or requested in RETIRED_MODELS:
        return DEFAULT_MODEL
    return requested


class GroqChat:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = (
            api_key if api_key is not None else os.getenv("GROQ_API_KEY", "")
        ).strip()
        self.model = select_model(
            model if model is not None else os.getenv("GROQ_MODEL", DEFAULT_MODEL)
        )
        self.history: list[dict[str, str]] = []

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def ask(self, message: str) -> str:
        if not self.available:
            return (
                "Consigo executar comandos locais agora. Para conversar livremente, "
                "configure GROQ_API_KEY no arquivo .env e reinicie a Ângela."
            )

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(self.history[-12:])
        messages.append({"role": "user", "content": message})
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.5,
            "max_completion_tokens": 400,
        }
        req = Request(
            API_URL,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "Angela-IA/0.3",
            },
            method="POST",
        )
        try:
            with urlopen(req, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
            answer = str(body["choices"][0]["message"]["content"] or "").strip()
            if not answer:
                return "A IA não retornou uma resposta. Tente novamente."
            self.history.extend([
                {"role": "user", "content": message},
                {"role": "assistant", "content": answer},
            ])
            self.history = self.history[-12:]
            return answer
        except HTTPError as exc:
            if exc.code == 401:
                return "A chave Groq foi recusada. Confira GROQ_API_KEY no arquivo .env."
            if exc.code == 429:
                return "O limite gratuito da Groq foi atingido. Tente mais tarde."
            if exc.code == 404:
                return (
                    f"Modelo Groq '{self.model}' indisponível (HTTP 404). "
                    "Confira GROQ_MODEL no .env. Sugestão: openai/gpt-oss-20b."
                )
            return f"Falha na consulta ao Groq (HTTP {exc.code})."
        except (URLError, TimeoutError):
            return "Não foi possível conectar à IA. Confira sua conexão com a internet."
        except (KeyError, IndexError, TypeError, ValueError):
            return "A IA retornou dados inesperados. Tente novamente."
