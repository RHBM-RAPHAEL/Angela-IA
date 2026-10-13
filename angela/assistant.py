"""Coordenação entre intenções locais seguras e conversa remota."""
from __future__ import annotations

from .actions import ActionDispatcher, detect_action, normalize
from .chat import GroqChat
from .windows_controller import WindowsController

HELP_MESSAGE = (
    "Posso abrir a calculadora, o Bloco de Notas, o Explorador e o VS Code; "
    "também posso alterar o tema claro ou escuro do Windows. "
    "Posso procurar aplicativos instalados, abrir pastas por caminho e pedir confirmação antes de fechar janelas. "
    "Se configurar a chave Groq, também podemos conversar sobre outros assuntos."
)


class AssistantEngine:
    def __init__(
        self, actions: ActionDispatcher | None = None, chat: GroqChat | None = None
    ) -> None:
        self.actions = actions if actions is not None else ActionDispatcher()
        self.chat = chat if chat is not None else GroqChat()
        self.windows = WindowsController()

    def reply(self, message: str) -> str:
        message = message.strip()
        if not message:
            return "Escreva uma mensagem ou utilize o botão Ouvir."

        # Confirmações e escolhas pendentes têm prioridade sobre novos
        # comandos para impedir fechamento de janelas sem autorização.
        if self.windows.pending is not None:
            pending_reply = self.windows.process(message)
            if pending_reply is not None:
                return pending_reply

        action = detect_action(message)
        if action:
            return self.actions.perform(action)

        local_reply = self.windows.process(message)
        if local_reply is not None:
            return local_reply

        clean = normalize(message).strip(" .,!?")
        if clean in {"oi", "ola", "ola angela", "bom dia", "boa tarde", "boa noite"}:
            return "Olá! Eu sou a Ângela. Como posso ajudar?"
        if clean in {"ajuda", "comandos", "o que voce faz", "o que voce pode fazer"}:
            return HELP_MESSAGE
        return self.chat.ask(message)
