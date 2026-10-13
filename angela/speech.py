"""Reconhecimento de voz local opcional; síntese feminina via Edge TTS online."""
from __future__ import annotations

import asyncio
from functools import lru_cache
import json
from pathlib import Path
import queue
import tempfile
import threading
import time

from .download_model import MODEL_PATH

_VOICE = "pt-BR-FranciscaNeural"
_SPEAK_LOCK = threading.Lock()


@lru_cache(maxsize=1)
def _get_model(model_path: str):
    from vosk import Model
    return Model(model_path)


def listen_once(seconds: float = 8.0) -> str:
    """Grava apenas enquanto solicitado. Não envia áudio para a nuvem."""
    if not MODEL_PATH.is_dir():
        raise FileNotFoundError(
            "Modelo de voz não instalado. Rode: python -m angela.download_model"
        )

    import sounddevice as sd
    from vosk import KaldiRecognizer

    recognizer = KaldiRecognizer(_get_model(str(MODEL_PATH)), 16000)
    chunks: queue.Queue[bytes] = queue.Queue()

    def on_audio(indata, frames, timestamp, status):
        chunks.put(bytes(indata))

    with sd.RawInputStream(
        samplerate=16000, blocksize=4000, dtype="int16",
        channels=1, callback=on_audio,
    ):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            try:
                data = chunks.get(timeout=0.25)
            except queue.Empty:
                continue
            if recognizer.AcceptWaveform(data):
                phrase = json.loads(recognizer.Result()).get("text", "").strip()
                if phrase:
                    return phrase
    return json.loads(recognizer.FinalResult()).get("text", "").strip()


def speak(text: str) -> None:
    """Voz feminina pt-BR. Requer acesso ao serviço online de síntese de voz."""
    if not text.strip():
        return
    import edge_tts
    import pygame

    with _SPEAK_LOCK:
        with tempfile.TemporaryDirectory(prefix="angela_voice_") as temp_dir:
            output = Path(temp_dir) / "fala.mp3"
            asyncio.run(edge_tts.Communicate(text[:1800], _VOICE).save(str(output)))
            try:
                pygame.mixer.init()
                pygame.mixer.music.load(str(output))
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.05)
            finally:
                if pygame.mixer.get_init():
                    pygame.mixer.music.stop()
                    pygame.mixer.music.unload()
                    pygame.mixer.quit()
