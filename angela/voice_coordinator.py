"""Integração opcional de wake word, fala e processamento com a esfera.

Não abre outro painel, não grava áudio, e só inicia microfone ao ser ativada.
Todos os eventos de interface passam pela fila Qt do processo principal.
"""
from __future__ import annotations

import queue
import re
import threading
import time
from datetime import datetime
from random import SystemRandom

from .states import AngelaState
from .wake import WakeListener
from .conversation_flow import invites_answer, wants_to_end
from .audit_log import record, begin_interaction, set_interaction
from .perf_metrics import metric, measure_ms

_RANDOM = SystemRandom()


def greeting(now=None):
    now = now or datetime.now()
    period = "bom dia" if 5 <= now.hour < 12 else "boa tarde" if 12 <= now.hour < 18 else "boa noite"
    return _RANDOM.choice((
        f"Oi! {period.capitalize()}. Estou te ouvindo.",
        f"{period.capitalize()}! Pode falar comigo.",
        f"Oi, {period}. O que você gostaria de fazer?",
        f"Olá! {period.capitalize()}. Estou aqui, pode falar.",
    ))


class VoiceCoordinator:
    """Recebe eventos da escuta e executa voz/IA fora da thread gráfica."""

    def __init__(self, set_state, on_message=None):
        self.set_state = set_state
        self.on_message = on_message or (lambda message: print("ANGELA_REPLY", ascii(message), flush=True))
        self.events = queue.Queue()
        self.listener = WakeListener(lambda kind, value: self.events.put((kind, value)))
        self.active = False
        self.busy = False
        self.engine = None
        self.activated_once = False
        self.on_voice_level = lambda value: None
        self.on_mic_level = lambda value: None
        self.on_microphone_status = lambda message: None
        self.on_camera_status = lambda message: None
        self.awaiting_answer = False
        self.conversation_closed = False
        self.trace_id = None
        self._wake_activated_ns = None
        self._command_ready_ns = None
        self.on_panel = lambda payload: None
        self.on_result_view = lambda payload: None
        self.on_transcript = lambda payload: None
        self.on_understanding = lambda text: None
        self.on_reply = lambda payload: None
        self.on_feedback = lambda accepted: None
        self.feedback_pending = False
        self._next_reportable = False
        self.on_feedback_prompt = lambda visible: None
        self.on_feedback_text = lambda text: None
        # Invalida resultados de workers iniciados em sessões anteriores.
        self._session_epoch = 0
        self._engine_lock = threading.Lock()

    def _emit_if_current(self, epoch, kind, value):
        if self.active and epoch == self._session_epoch:
            self.events.put((kind, value))

    def _discard_pending_events(self):
        while True:
            try:
                self.events.get_nowait()
            except queue.Empty:
                return

    def accept_feedback(self, accepted: bool) -> bool:
        if not self.feedback_pending:
            return False
        self.feedback_pending = False
        self.on_feedback(bool(accepted))
        self.on_feedback_prompt(False)
        return True

    def start(self):
        if self.active:
            return
        self._session_epoch += 1
        self._discard_pending_events()
        self.active = True
        record('session_start', voice_enabled=True)
        self.set_state(AngelaState.STARTING)
        self.listener.start()

    def stop(self):
        record('session_stop')
        self.active = False
        self._session_epoch += 1
        self.busy = False
        self.awaiting_answer = False
        self.feedback_pending = False
        self._next_reportable = False
        self.listener.stop()
        self._discard_pending_events()
        self._wake_activated_ns = None
        self._command_ready_ns = None

    def listen_follow_up(self):
        self.busy = False
        if self.active:
            self.set_state(AngelaState.LISTENING)
            self.listener.resume(follow_up=True)

    def _speak_async(self, message, follow_up):
        epoch = self._session_epoch
        trace_id = self.trace_id
        command_ready_ns = self._command_ready_ns
        def work():
            if not self.active or epoch != self._session_epoch:
                return
            started = time.perf_counter()
            try:
                from .speech import speak
                from .command_quality import speech_summary
                voice_text = speech_summary(message, limit=225)
                set_interaction(trace_id)
                record('speech_attempt', method='edge_tts', provider='auto', characters=len(voice_text))
                def first_audio():
                    if command_ready_ns is not None:
                        metric("voice_end_to_audio", measure_ms(command_ready_ns))
                voice_used = speak(voice_text, provider="auto", on_level=lambda value: self._emit_if_current(epoch, "voice_level", value), on_first_audio=first_audio)
                duration = round((time.perf_counter()-started)*1000)
                metric("tts_total", duration)
                record('speech_result', status='success', provider=voice_used, duration_ms=duration)
                print('ANGELA_TIMING voice_total_ms', round((time.perf_counter()-started)*1000), 'provider', voice_used, flush=True)
                self._emit_if_current(epoch, "finished_speech", "followup" if follow_up else "normal")
            except Exception as exc:
                record('speech_result', status='failure', error_type=type(exc).__name__)
                self._emit_if_current(epoch, "voice_failure", type(exc).__name__)
        threading.Thread(target=work, daemon=True).start()

    def _reply_async(self, message):
        epoch = self._session_epoch
        trace_id = self.trace_id
        def work():
            started = time.perf_counter()
            set_interaction(trace_id)
            record('command_received', transcript=message)
            print('ANGELA_COMMAND_RECEIVED', repr(message), flush=True)
            try:
                # Não execute um comando da sessão anterior após parar/reiniciar.
                # O lock protege o estado mutável e o histórico do engine.
                with self._engine_lock:
                    if not self.active or epoch != self._session_epoch:
                        return
                    if self.engine is None:
                        from .assistant import AssistantEngine
                        self.engine = AssistantEngine()
                    self.engine.on_camera_status = (
                        lambda status: self._emit_if_current(
                            epoch, 'camera_status', status
                        )
                    )
                    reply = self.engine.reply(message)
                    interpretation = self.engine.last_interpretation
                    reportable = bool(self.engine.last_execution)
                    panel = self.engine.last_panel
                    result_view = self.engine.last_result_view
                if interpretation:
                    self._emit_if_current(epoch, 'understanding', interpretation)
                self._emit_if_current(epoch, 'execution_reportable', reportable)
                if panel is not None:
                    self._emit_if_current(epoch, 'panel', panel)
                if result_view is not None:
                    self._emit_if_current(epoch, 'result_view', result_view)
                duration = round((time.perf_counter()-started)*1000)
                metric("command_dispatch", duration)
                record('command_result', reply=reply, duration_ms=duration)
                print('ANGELA_TIMING reply_ms', round((time.perf_counter()-started)*1000), flush=True)
                print('ANGELA_COMMAND_RESULT', repr(reply[:160]), flush=True)
                self._emit_if_current(epoch, "reply", reply)
            except Exception as exc:
                record('command_failure', error_type=type(exc).__name__)
                self._emit_if_current(epoch, "engine_failure", type(exc).__name__)
        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        while True:
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break

            if kind == 'understanding':
                self.on_understanding(value)
            elif kind == 'execution_reportable':
                self._next_reportable = bool(value)
            elif kind == 'panel':
                self.on_panel(value)
            elif kind == 'result_view' and self.active:
                try:
                    self.on_result_view(value)
                except Exception as exc:
                    # Falha na janela nao pode interromper TTS ou escuta.
                    record('result_view_failure', error_type=type(exc).__name__)
            elif kind == "voice_level":
                self.on_voice_level(value)
            elif kind == "mic_level":
                if self.active and not self.busy:
                    self.on_mic_level(value)
            elif kind == 'camera_status':
                self.on_camera_status(value)
            elif kind == "wake_ready":
                if self.active and not self.busy:
                    self.set_state(AngelaState.READY)
                    self.on_microphone_status("Microfone ligado · diga Ângela")
                    print("ANGELA_MIC_READY", flush=True)
            elif kind == "wake_activated" and self.active and not self.busy:
                self.trace_id = begin_interaction()
                self._wake_activated_ns = time.perf_counter_ns()
                record('wake_activated')
                self.conversation_closed = False
                self.listener.pause()
                if not self.activated_once:
                    self.activated_once = True
                    # A saudação TTS online pode levar 10-20 segundos.
                    # Durante esse intervalo o microfone ficava pausado,
                    # parecendo desligado. Entrar direto em escuta evita
                    # perder os comandos ditos logo após "Ângela".
                    record('wake_first_activation', response='listen_immediately')
                self.listen_follow_up()
            elif kind == "wake_command" and self.active and not self.busy:
                if not self.trace_id:
                    self.trace_id = begin_interaction()
                set_interaction(self.trace_id)
                self._command_ready_ns = time.perf_counter_ns()
                if self._wake_activated_ns is not None:
                    metric("wake_to_command", measure_ms(self._wake_activated_ns, self._command_ready_ns))
                    self._wake_activated_ns = None
                record('heard', transcript=value)
                from .actions import normalize
                feedback_text = " ".join(re.sub(r"[^a-z0-9 ]+", " ", normalize(value)).split())
                if self.feedback_pending and feedback_text in {'sim', 'sim era', 'sim isso', 'era isso', 'isso mesmo', 'correto', 'nao', 'nao nao era', 'nao era', 'nao foi isso', 'errado'}:
                    accepted = feedback_text in {'sim', 'sim era', 'sim isso', 'era isso', 'isso mesmo', 'correto'}
                    self.on_feedback_text(value)
                    self.accept_feedback(accepted)
                    self.busy = False
                    self.set_state(AngelaState.READY)
                    self.listener.resume()
                    continue
                self.feedback_pending = False
                self._next_reportable = False
                self.on_feedback_prompt(False)
                self.on_transcript(value)
                self.busy = True
                self.listener.pause()
                if wants_to_end(value):
                    record('conversation_closed', transcript=value)
                    self.awaiting_answer = False
                    self.conversation_closed = True
                    self.busy = False
                    self.set_state(AngelaState.READY)
                    self.listener.resume()
                    continue
                self.conversation_closed = False
                self.set_state(AngelaState.PROCESSING)
                self._reply_async(value)
            elif kind == "reply":
                if not self.active:
                    continue
                set_interaction(self.trace_id)
                record('reply_prepared', text=value)
                self.on_reply(value)
                self.feedback_pending = self._next_reportable
                self._next_reportable = False
                self.on_feedback_prompt(self.feedback_pending)
                self.awaiting_answer = not self.conversation_closed and invites_answer(value)
                try:
                    self.on_message(value)
                except (UnicodeError, OSError) as exc:
                    print("ANGELA_LOG_ERROR", type(exc).__name__, flush=True)
                self.set_state(AngelaState.SPEAKING)
                self._speak_async(value, follow_up=False)
            elif kind == "finished_speech":
                set_interaction(self.trace_id)
                record('speech_finished', follow_up=value)
                self.busy = False
                if self.active:
                    if value == "followup" or self.awaiting_answer or self.feedback_pending:
                        self.awaiting_answer = False
                        self.listen_follow_up()
                    else:
                        self.set_state(AngelaState.READY)
                        self.listener.resume()
            elif kind == "wake_timeout" and self.active and not self.busy:
                self.set_state(AngelaState.READY)
            elif kind in ("wake_error", "voice_failure", "engine_failure"):
                record('runtime_error', kind=kind, error_type=value)
                print("ANGELA_DIAGNOSTIC", kind, value, flush=True)
                self.busy = False
                if kind == "wake_error":
                    self.active = False
                    self.listener.stop()
                if kind == 'wake_error':
                    self.set_state(AngelaState.STARTING)
                    self.on_microphone_status("Microfone indisponível — verifique a entrada de áudio")
                else:
                    self.set_state(AngelaState.READY)
                    if self.active:
                        self.listener.resume()
