"""Ativação opcional e local pela palavra 'Angela' com Vosk.

A escuta contínua é DESLIGADA por padrão. Não grava áudio em disco.
Nunca executa comandos diretamente: somente emite textos para a interface.
"""
from __future__ import annotations

import json
import queue
import re
import threading
import time
from typing import Callable

from .actions import normalize


_WAKE_PATTERN = re.compile(
    r"^(?:(?:oi|ola|ei)[,\s]+)?(?:angela|anjela)(?:\b|$)[\s,!.?:;-]*(.*)$"
)


def extract_wake_command(text: str) -> str | None:
    """Retorna o restante do comando, '' para nome isolado, None sem ativação."""
    cleaned = normalize(text).strip()
    match = _WAKE_PATTERN.match(cleaned)
    if match is None:
        return None
    # Preserve a frase original após o nome, quando possível, para a IA.
    # A remoção de acentos é usada somente para reconhecer a ativação.
    original = re.match(
        r"^(?:(?:oi|olá|ola|ei)[,\s]+)?(?:ângela|angela|anjela)\b[\s,!.?:;-]*(.*)$",
        text.strip(), flags=re.IGNORECASE,
    )
    return (original.group(1) if original else match.group(1)).strip()


class WakePhraseParser:
    """Máquina de estados independente de áudio, totalmente testável."""

    def __init__(self, follow_up_seconds: float = 10.0):
        self.follow_up_seconds = follow_up_seconds
        self.deadline: float | None = None

    def reset(self) -> None:
        self.deadline = None

    def arm_follow_up(self, now: float) -> None:
        self.deadline = now + self.follow_up_seconds

    def expired(self, now: float) -> bool:
        if self.deadline is not None and now >= self.deadline:
            self.deadline = None
            return True
        return False

    def accept(self, text: str, now: float) -> tuple[str, str] | None:
        text = text.strip()
        if not text:
            return None

        self.expired(now)
        command = extract_wake_command(text)
        if command is not None:
            if command:
                self.reset()
                return "wake_command", command
            self.arm_follow_up(now)
            return "wake_activated", ""

        if self.deadline is not None:
            self.reset()
            return "wake_command", text
        return None


class WakeListener:
    """Executa o reconhecimento no microfone em uma thread separada."""

    def __init__(
        self,
        on_event: Callable[[str, str], None],
        follow_up_seconds: float = 10.0,
    ) -> None:
        self.on_event = on_event
        self.follow_up_seconds = follow_up_seconds
        self._stop = threading.Event()
        self._paused = threading.Event()
        self._reset = threading.Event()
        self._followup = threading.Event()
        self._listening_for_command = False
        self._mic_peak = 0.0
        self._thread: threading.Thread | None = None
        self._state_lock = threading.Lock()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> bool:
        with self._state_lock:
            if self.running:
                return False
            self._stop.clear()
            self._paused.clear()
            self._reset.clear()
            self._followup.clear()
            self._thread = threading.Thread(
                target=self._run, daemon=True, name="AngelaWakeListener",
            )
            self._thread.start()
            return True

    def pause(self) -> None:
        self._paused.set()
        self._listening_for_command = False

    def resume(self, follow_up: bool = False) -> None:
        # Reseta o reconhecedor para evitar áudio antigo/self-trigger.
        if follow_up:
            self._followup.set()
        self._reset.set()
        self._paused.clear()

    def stop(self) -> None:
        self._stop.set()
        self._paused.set()
        thread = self._thread
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=1.5)

    def _run(self) -> None:
        audio: queue.Queue[bytes] = queue.Queue(maxsize=24)
        parser = WakePhraseParser(self.follow_up_seconds)

        def callback(indata, frames, timestamp, status):
            if self._stop.is_set() or self._paused.is_set():
                return
            # Read the existing Vosk microphone stream: no second mic device.
            if self._listening_for_command:
                import audioop
                level = min(1.0, audioop.rms(bytes(indata), 2) / 9000.0)
                self._mic_peak = max(level, self._mic_peak * 0.55)
                self.on_event('mic_level', self._mic_peak)
            try:
                audio.put_nowait(bytes(indata))
            except queue.Full:
                # Um transbordamento é preferível a travar a thread de áudio.
                pass

        try:
            from vosk import KaldiRecognizer
            from sounddevice import RawInputStream
            from .download_model import MODEL_PATH
            from .speech import _get_model

            if not MODEL_PATH.is_dir():
                raise FileNotFoundError(
                    "Modelo Vosk não instalado. Execute python -m angela.download_model"
                )

            model = _get_model(str(MODEL_PATH))
            wake_grammar = json.dumps(['angela', 'anjela', 'oi angela', 'ei angela', 'angela abra a calculadora', '[unk]'], ensure_ascii=False)
            recognizer = KaldiRecognizer(model, 16000, wake_grammar)
            with RawInputStream(
                samplerate=16000, blocksize=4000, dtype="int16",
                channels=1, callback=callback,
            ):
                if not self._stop.is_set():
                    self.on_event("wake_ready", "")
                while not self._stop.is_set():
                    if self._paused.is_set():
                        self._reset.set()
                        try:
                            while True:
                                audio.get_nowait()
                        except queue.Empty:
                            pass
                        self._stop.wait(0.06)
                        continue

                    if self._reset.is_set():
                        self._listening_for_command = self._followup.is_set()
                        self._mic_peak = 0.0
                        recognizer = (KaldiRecognizer(model, 16000) if self._listening_for_command
                                      else KaldiRecognizer(model, 16000, wake_grammar))
                        parser.reset()
                        if self._listening_for_command:
                            parser.arm_follow_up(time.monotonic())
                            self._followup.clear()
                        self._reset.clear()
                        try:
                            while True:
                                audio.get_nowait()
                        except queue.Empty:
                            pass

                    try:
                        chunk = audio.get(timeout=0.2)
                    except queue.Empty:
                        if parser.expired(time.monotonic()):
                            self._listening_for_command = False
                            self._reset.set()
                            self.on_event("wake_timeout", "")
                        continue

                    if recognizer.AcceptWaveform(chunk):
                        recognized = json.loads(recognizer.Result()).get("text", "")
                        print('ANGELA_HEARD', repr(recognized), flush=True)
                        event = parser.accept(recognized, time.monotonic())
                        if event:
                            kind, text = event
                            if self._listening_for_command and kind == 'wake_command':
                                self._listening_for_command = False
                            if kind == "wake_command":
                                # Suspende imediatamente para não disparar duas ações.
                                self.pause()
                            self.on_event(kind, text)
                    elif parser.expired(time.monotonic()):
                        self._listening_for_command = False
                        self._reset.set()
                        self.on_event("wake_timeout", "")
        except Exception as exc:
            if not self._stop.is_set():
                # Sem dump de dispositivos nem stack trace sensível.
                self.on_event(
                    "wake_error",
                    f"Não foi possível iniciar o microfone contínuo: "
                    f"{type(exc).__name__}: {str(exc)[:160]}",
                )
        finally:
            self.on_event("wake_stopped", "")
