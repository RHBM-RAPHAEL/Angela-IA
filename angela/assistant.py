"""Coordenação entre intenções locais seguras e conversa remota."""
from __future__ import annotations

from .actions import ActionDispatcher, detect_action, normalize
from .chat import GroqChat
from .windows_controller import WindowsController, command_kind
from .tool_executor import WindowsToolExecutor, plan_tool
from .sequence_executor import plan_sequence, execute_sequence
from .project_tools import handle_project_request, parse_project_request
from .audit_log import record
from .windows_resources import resource_request, open_resource
from .agent_planner import plan_via_groq, execute_plan, local_fallback_plan
from .speech_corrections import correct_transcript
from .speech_understanding import normalize_intent, unknown_speech
from .command_clarification import CommandClarification
from .intent_confirmation import IntentConfirmation
from .project_listing import list_request, list_folders, listing_reply
from .adaptive_memory import preference_request, save_preference, load_preferences
from .command_quality import normalize_request, clock_request, local_clock_reply, browser_intent, execution_feedback_eligible
from .screen_vision import (
    parse_vision_request, confirmation_decision, analyze_screen,
    VisionRequest,
)
import time

HELP_MESSAGE = (
    "Posso abrir a calculadora, o Bloco de Notas, o Explorador e o VS Code; "
    "também posso alterar o tema claro ou escuro do Windows. "
    "Posso procurar aplicativos instalados, abrir pastas por caminho e pedir confirmação antes de fechar janelas. "
    "Posso também analisar a janela ativa ou a tela inteira sob demanda, "
    "sempre pedindo confirmação antes de enviar uma captura à IA Groq. "
    "Se configurar a chave Groq, também podemos conversar sobre outros assuntos."
)


class AssistantEngine:
    def __init__(
        self, actions: ActionDispatcher | None = None, chat: GroqChat | None = None
    ) -> None:
        self.actions = actions if actions is not None else ActionDispatcher()
        self.chat = chat if chat is not None else GroqChat()
        self.windows = WindowsController()
        self.tools = WindowsToolExecutor()
        self.confirmation = IntentConfirmation()
        self.clarification = CommandClarification()
        self.last_interpretation = None
        self.last_panel = None
        self.last_execution = False
        self._vision_pending: tuple[VisionRequest, float] | None = None

    def _as_action(self, result: str) -> str:
        self.last_execution = execution_feedback_eligible(result, True)
        # Uma tarefa local concluída não deve contaminar o contexto remoto.
        history = getattr(self.chat, 'history', None)
        if isinstance(history, list):
            history.clear()
        return result

    def reply(self, message: str) -> str:
        message = message.strip()
        heard_message = message
        self.last_panel = None
        self.last_execution = False
        self.last_interpretation = None
        if not message:
            return "Escreva uma mensagem ou utilize o botão Ouvir."

        if unknown_speech(message):
            record('speech_not_understood', transcript=message)
            return 'Não consegui entender o que você disse. Pode repetir mais devagar?'

        # Captura somente após autorização explícita para CADA pergunta.
        # Confirmações visuais precedem a lógica de fechar janelas e aplicativos.
        pending = self._vision_pending
        if pending is not None:
            self._vision_pending = None
            request, expires = pending
            decision = confirmation_decision(message)
            if decision is False:
                record('vision_consent', approved=False)
                return 'Certo, não vou capturar nem enviar sua tela.'
            if decision is True:
                if time.monotonic() > expires:
                    return 'A autorização para analisar a tela expirou. Peça novamente.'
                if not getattr(self.chat, 'available', False):
                    return 'Não consigo analisar imagens sem uma chave Groq configurada.'
                record('vision_consent', approved=True, scope=request.scope)
                # Sem guardar a imagem no histórico, no disco ou no log.
                return analyze_screen(request, self.chat.api_key)
            # Outro assunto cancela a autorização anterior sem captura.

        screen_request = parse_vision_request(message)
        if screen_request is not None:
            if not getattr(self.chat, 'available', False):
                return ('Para entender imagens da tela, preciso que GROQ_API_KEY '
                        'esteja configurada. Não fiz nenhuma captura.')
            self._vision_pending = (screen_request, time.monotonic() + 75)
            scope = ('janela ativa' if screen_request.scope == 'window'
                     else 'tela inteira do monitor principal')
            record('vision_consent_requested', scope=screen_request.scope)
            return (
                f'Posso capturar uma imagem da {scope} e enviá-la à IA Groq '
                'para responder sua pergunta? Diga sim para permitir ou cancelar. '
                'Você autoriza?'
            )
        if clock_request(message):
            record('local_clock_requested')
            return local_clock_reply()
        clarified, new_message = self.clarification.resolve(message)
        if clarified:
            if not new_message or not new_message.startswith(('abra ', 'feche ')):
                return new_message or 'Diga novamente, por favor.'
            message = new_message
        handled, answer = self.confirmation.resolve(message)
        if handled:
            if answer and answer.startswith('Abra o VS Code'):
                record('app_intent_confirmed', target='VS Code')
                return self._as_action(self.actions.perform('vscode'))
            if answer and answer.startswith('Abra o Spotify'):
                record('app_intent_confirmed', target='Spotify')
                result = self.windows.process('abra o spotify')
                if result is not None:
                    return self._as_action(result) if result.startswith(('Solicitei', 'Abri')) else result
                return 'Não consegui localizar o Spotify nos aplicativos instalados.'
            return answer
        original = message
        message = normalize_intent(normalize_request(correct_transcript(message)))
        if message != heard_message:
            self.last_interpretation = message
        guessed = self.confirmation.propose(message)
        if guessed:
            return guessed
        preference = preference_request(message)
        if preference is not None:
            key, value = preference
            save_preference(key, value)
            record('user_preference_updated', key=key, enabled=value)
            return 'Certo. Vou responder de forma mais curta.' if value else 'Certo. Voltei ao modo normal de respostas.'
        if original != message:
            record('speech_interpreted', original=original, interpreted=message)
        ask_for_target = self.clarification.ask_if_needed(message)
        if ask_for_target is not None:
            return ask_for_target

        folder = list_request(message)
        if folder is not None:
            try:
                names = list_folders(folder)
            except (OSError, PermissionError):
                return 'Não consegui consultar essa pasta autorizada.'
            self.last_panel = {'title': 'Projetos · Meus Softwares', 'items': names}
            record('project_folder_listing', folder=str(folder), count=len(names))
            return self._as_action(listing_reply(names))

        # Um novo pedido explícito cancela escolhas antigas. Apenas respostas
        # curtas como 'sim', 'não' e números continuam a confirmação pendente.
        action = detect_action(message)
        tool_request = plan_tool(message)
        sequence = plan_sequence(message)
        project_request = parse_project_request(message)
        resource = resource_request(message)
        if self.windows.pending is not None:
            if action is not None or tool_request is not None or sequence is not None or project_request is not None:
                self.windows.pending = None
            else:
                pending_reply = self.windows.process(message)
                if pending_reply is not None:
                    return self._as_action(pending_reply) if pending_reply.startswith(('Solicitei', 'Abri ')) else pending_reply

        if resource is not None:
            return self._as_action(open_resource(resource))

        # O Vosk confunde 'no Opera' com 'não Opera'. Sem confirmação,
        # jamais escolher um navegador para uma negação ambígua.
        site_intent = browser_intent(message)
        if site_intent is not None and site_intent[1] == 'ask':
            return 'Você quis dizer no Opera ou sem o Opera? Diga o navegador desejado.'
        if site_intent is not None and 'canal do youtube' in normalize(message):
            return 'Qual é o nome exato do canal do YouTube que deseja abrir?'

        # Abertura de sites tem prioridade sobre a busca de aplicativos.
        # Ex.: 'abra o youtube pelo opera' nao e nome de aplicativo.
        from .agent_planner import local_fallback_plan
        website_plan = local_fallback_plan(message)
        if website_plan:
            record('agent_local_site_plan', steps=website_plan)
            return self._as_action(execute_plan(website_plan, self.windows))

        if project_request is not None:
            record('action_attempt', method='project_lookup', target=project_request)
            result = handle_project_request(message)
            record('action_result', method='project_lookup', target=project_request, result=result)
            return self._as_action(result)

        if sequence is not None:
            record('action_attempt', method='sequence', steps=sequence)
            result = execute_sequence(sequence, self.actions, self.windows)
            record('action_result', method='sequence', result=result)
            return self._as_action(result)

        if action:
            record('action_attempt', method='action_dispatcher', action=action)
            result = self.actions.perform(action)
            record('action_result', method='action_dispatcher', action=action, result=result)
            return self._as_action(result)

        if tool_request is not None:
            record('action_attempt', method='allowlisted_windows_tool', action=tool_request.action, target=tool_request.target)
            result = self.tools.run(tool_request)
            record('action_result', method='allowlisted_windows_tool', result=result)
            return self._as_action(result) if tool_request.action == 'read_command' else result

        record('routing_attempt', method='windows_controller', transcript=message)
        local_reply = self.windows.process(message)
        if local_reply is not None:
            record('action_result', method='windows_controller', result=local_reply)
            kind = command_kind(message)
            if (kind is not None and kind[0] != 'unsupported_send'
                    and 'confirmar fechamento' not in normalize(local_reply)
                    and not local_reply.startswith(('Qual ', 'Diga ', 'Encontrei várias'))):
                return self._as_action(local_reply)
            return self._as_action(local_reply) if local_reply.startswith(('Solicitei', 'Abri ')) else local_reply

        clean = normalize(message).strip(" .,!?")
        if clean in {"oi", "ola", "ola angela", "bom dia", "boa tarde", "boa noite"}:
            return "Estou ouvindo."
        if clean in {"ajuda", "comandos", "o que voce faz", "o que voce pode fazer"}:
            return HELP_MESSAGE
        # Perguntas informativas seguem para conversa; não consumir cota
        # do planejador de ações (que pode retornar HTTP 403).
        needs_plan = bool(__import__('re').search(
            r'\b(?:abra|abre|abrir|feche|fecha|fechar|inicie|inicia|acesse|entre|mostre|configure)\b',
            normalize(message)))
        record('routing_attempt', method='agent_planner' if needs_plan else 'groq_chat_direct')
        plan = plan_via_groq(message, self.chat) if needs_plan else None
        if plan is None:
            plan = local_fallback_plan(message)
            if plan:
                record('agent_fallback_plan', steps=plan)
        if plan:
            return self._as_action(execute_plan(plan, self.windows))
        record('routing_attempt', method='groq_chat')
        return self.chat.ask(message)
