"""Ativação opcional e local pela palavra 'Angela' com Vosk.

A escuta contínua é DESLIGADA por padrão. Não grava áudio em disco.
Nunca executa comandos diretamente: somente emite textos para a interface.
"""
from __future__ import annotations

import json
import audioop
from collections import deque
import queue
import re
import threading
import time
from typing import Callable

from .actions import normalize
from .audio_frontend import AudioFrontend, capture_candidates
from .audit_log import record


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


def choose_wake_transcript(open_text: str, restricted_text: str) -> str:
    """Usa a transcrição livre se ela começa por Ângela.

    O gramático limitado é fallback para o nome isolado; o comando não se
    perde quando o usuário diz nome e instrução na mesma frase.
    """
    if extract_wake_command(open_text) is not None:
        return open_text
    return restricted_text


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
        audio: queue.Queue[bytes] = queue.Queue(maxsize=40)
        parser = WakePhraseParser(self.follow_up_seconds)

        def callback(indata, frames, timestamp, status):
            if self._stop.is_set() or self._paused.is_set():
                return
            # Nunca processar DSP ou callbacks Qt na thread de áudio realtime.
            try:
                audio.put_nowait(bytes(indata))
            except queue.Full:
                # Um transbordamento é preferível a travar a thread de áudio.
                pass

        try:
            from vosk import KaldiRecognizer
            import sounddevice as sd
            from .download_model import MODEL_PATH
            from .speech import _get_model

            if not MODEL_PATH.is_dir():
                raise FileNotFoundError(
                    "Modelo Vosk não instalado. Execute python -m angela.download_model"
                )

            model = _get_model(str(MODEL_PATH))
            wake_grammar = json.dumps([
                'angela', 'anjela', 'oi angela', 'ei angela',
                'olá angela', 'angela abra a calculadora', '[unk]'
            ], ensure_ascii=False)
            recognizer = KaldiRecognizer(model, 16000, wake_grammar)
            replay = deque(maxlen=80)  # últimos 8 segundos, somente em RAM
            stream = None
            selected = None
            startup_errors = []
            best_weak = None  # guarda a entrada mais forte se nenhuma atingir o limiar
            # Escolhe captura que entrega sinal real; drivers de matrizes
            # digitais podem devolver apenas zeros por certos endpoints.
            candidates = capture_candidates(sd)
            for position, config in enumerate(candidates):
                try:
                    stream = sd.RawInputStream(
                        device=config.device, samplerate=config.sample_rate,
                        blocksize=int(config.sample_rate * 0.10),
                        dtype="int16", channels=config.channels, callback=callback,
                    )
                    stream.start()
                    # Avalia apenas a intensidade por 450 ms: nunca grava áudio.
                    peak_rms = 0
                    probe_end = time.monotonic() + 0.45
                    while time.monotonic() < probe_end:
                        try:
                            sample = audio.get(timeout=0.1)
                            peak_rms = max(peak_rms, audioop.rms(sample, 2))
                        except queue.Empty:
                            pass
                    record('microphone_probe', source=config.source,
                           device_index=config.device, peak_rms=peak_rms)
                    print('ANGELA_MIC_PROBE', config.source, config.device,
                          peak_rms, flush=True)
                    # Não aceitar o primeiro canal que apresenta somente
                    # ruído residual. Alguns canais WDM-KS entregam RMS < 20
                    # mesmo sem captar a voz: tentar os seguintes.
                    if peak_rms < 24:
                        if best_weak is None or peak_rms > best_weak[1]:
                            best_weak = (config, peak_rms)
                        stream.stop()
                        stream.close()
                        stream = None
                        continue
                    selected = config
                    break
                except (OSError, ValueError, RuntimeError, sd.PortAudioError) as exc:
                    startup_errors.append(type(exc).__name__)
                    if stream is not None:
                        try:
                            stream.close()
                        except OSError:
                            pass
                        stream = None
            if stream is None and best_weak is not None:
                # Se a sala estiver totalmente silenciosa, ainda permitir
                # a captura pela melhor entrada que conseguiu abrir.
                config, weak_rms = best_weak
                stream = sd.RawInputStream(
                    device=config.device, samplerate=config.sample_rate,
                    blocksize=int(config.sample_rate * 0.10),
                    dtype="int16", channels=config.channels, callback=callback,
                )
                stream.start()
                selected = config
                record("microphone_weak_fallback", source=config.source,
                       device_index=config.device, peak_rms=weak_rms)
            if stream is None or selected is None:
                raise RuntimeError("Nenhuma entrada de microfone disponível: " + ",".join(startup_errors))
            frontend = AudioFrontend(selected.sample_rate, input_channels=selected.channels)
            record('microphone_open', source=selected.source, sample_rate=selected.sample_rate,
                   device_index=selected.device, input_channels=selected.channels,
                   max_gain=frontend.agc.max_gain)
            print('ANGELA_MIC_SOURCE', selected.source, selected.device,
                  selected.sample_rate, selected.channels, flush=True)
            last_metrics = time.monotonic()
            last_level_emit = 0.0
            try:
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
                        replay.clear()
                        frontend.reset()
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

                    processed = frontend.process(chunk)
                    if not processed:
                        continue
                    # Mostra captação também ANTES da palavra de ativação.
                    # Na implementação anterior a aura só reagia após "Ângela",
                    # dando a impressão de que o microfone estava desligado.
                    now = time.monotonic()
                    if now - last_level_emit >= 0.14:
                        noise_floor = max(12.0, frontend.agc.ambient_rms * 1.7)
                        useful_rms = max(0.0, frontend.agc.last_output_rms - noise_floor)
                        level = min(1.0, (useful_rms / 600.0) ** 0.5)
                        self._mic_peak = max(level, self._mic_peak * 0.68)
                        self.on_event('mic_level', self._mic_peak)
                        last_level_emit = now
                    if now - last_metrics >= 6.0:
                        record('mic_signal_level', rms_in=frontend.agc.last_input_rms,
                               rms_out=frontend.agc.last_output_rms,
                               gain=round(frontend.agc.gain, 2),
                               ambient=round(frontend.agc.ambient_rms),
                               queue_depth=audio.qsize())
                        last_metrics = now
                    if not self._listening_for_command:
                        replay.append(processed)
                    complete = recognizer.AcceptWaveform(processed)
                    if complete:
                        recognized = json.loads(recognizer.Result()).get("text", "")
                        if not self._listening_for_command:
                            # Só usa a decodificação livre após um segmento
                            # finalizado, nunca em paralelo continuamente.
                            if recognized and not self._stop.is_set():
                                extended = KaldiRecognizer(model, 16000)
                                for piece in replay:
                                    extended.AcceptWaveform(piece)
                                broad = json.loads(extended.FinalResult()).get("text", "")
                                recognized = choose_wake_transcript(broad, recognized)
                            replay.clear()
                        print('ANGELA_HEARD', repr(recognized), flush=True)
                        event = parser.accept(recognized, now)
                        if event:
                            kind, text = event
                            if self._listening_for_command and kind == 'wake_command':
                                self._listening_for_command = False
                            if kind == "wake_command":
                                # Suspende imediatamente para não disparar duas ações.
                                self.pause()
                            self.on_event(kind, text)
                    elif parser.expired(now):
                        self._listening_for_command = False
                        self._reset.set()
                        self.on_event("wake_timeout", "")
            finally:
                try:
                    stream.stop()
                    stream.close()
                except (OSError, RuntimeError, sd.PortAudioError):
                    pass
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
