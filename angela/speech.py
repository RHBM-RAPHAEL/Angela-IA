"""Entrada por microfone (Vosk) e saída de voz com fallback seguro."""
from __future__ import annotations

import asyncio
import base64
from functools import lru_cache
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time

from .download_model import MODEL_PATH

VOICE_TEST_SENTENCE = "Olá! Eu sou a Ângela. Este é um teste da minha voz feminina."
_VOICE = "pt-BR-FranciscaNeural"
_SPEAK_LOCK = threading.Lock()


class SpeechError(RuntimeError):
    """Falha de síntese de voz apresentada de forma segura no chat."""


@lru_cache(maxsize=1)
def _get_model(model_path: str):
    from vosk import Model
    return Model(model_path)


def listen_once(seconds: float = 8.0) -> str:
    """Grava somente quando solicitado; reconhece o áudio localmente."""
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


def _speak_kokoro(text: str) -> str:
    from .kokoro_local import speak_dora
    return speak_dora(text)


def _speak_edge(text: str) -> str:
    """Online: usa Francisca quando solicitada ou como última alternativa."""
    import edge_tts
    import pygame

    with tempfile.TemporaryDirectory(prefix="angela_voice_") as temp_dir:
        output = Path(temp_dir) / "fala.mp3"
        try:
            asyncio.run(edge_tts.Communicate(text, _VOICE).save(str(output)))
        except Exception as exc:
            # Não mostrar URLs de WebSocket com tokens temporários no chat.
            if "403" in str(exc):
                raise SpeechError(
                    "O servidor Edge TTS recusou a conexão (HTTP 403). "
                    "Use Dora (local) ou Windows (offline)."
                ) from None
            raise SpeechError(
                f"Falha no serviço Edge TTS ({type(exc).__name__}). "
                "Tente a voz local Dora."
            ) from None

        if not output.is_file() or output.stat().st_size == 0:
            raise SpeechError("O serviço Edge TTS não retornou áudio.")

        initialized = False
        loaded = False
        try:
            pygame.mixer.init()
            initialized = True
            pygame.mixer.music.load(str(output))
            loaded = True
            pygame.mixer.music.set_volume(1.0)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.05)
        finally:
            if initialized:
                pygame.mixer.music.stop()
                if loaded:
                    pygame.mixer.music.unload()
                pygame.mixer.quit()
    return "Francisca (português brasileiro, online)"


# Nunca interpolar texto ditado/gerado no código executado pelo PowerShell.
_WINDOWS_SAPI_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$txt = [System.Text.Encoding]::UTF8.GetString(
  [Convert]::FromBase64String($env:ANGELA_TTS_PAYLOAD)
)
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
  $voice = $synth.GetInstalledVoices() |
    Where-Object {
      $_.Enabled -and
      $_.VoiceInfo.Culture.Name -eq 'pt-BR' -and
      $_.VoiceInfo.Gender -eq 'Female'
    } |
    Select-Object -First 1
  if ($null -eq $voice) {
    Write-Error 'VOZ_PT_BR_FEMININA_NAO_INSTALADA'
    exit 12
  }
  $synth.SelectVoice($voice.VoiceInfo.Name)
  $synth.SetOutputToDefaultAudioDevice()
  $synth.Speak($txt)
  Write-Output ('ANGELA_VOICE=' + $voice.VoiceInfo.Name)
} finally {
  $synth.Dispose()
}
"""


def _speak_windows(text: str) -> str:
    if sys.platform != "win32":
        raise SpeechError("A voz Windows SAPI funciona somente no Windows.")
    env = os.environ.copy()
    env["ANGELA_TTS_PAYLOAD"] = base64.b64encode(text.encode("utf-8")).decode("ascii")
    try:
        proc = subprocess.run(
            [
                "powershell.exe", "-NoProfile", "-NonInteractive",
                "-Command", _WINDOWS_SAPI_SCRIPT,
            ],
            env=env, text=True, capture_output=True, timeout=45,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
    except FileNotFoundError as exc:
        raise SpeechError("PowerShell não encontrado.") from exc
    except subprocess.TimeoutExpired as exc:
        raise SpeechError("A voz do Windows demorou demais para responder.") from exc

    if proc.returncode != 0:
        if "VOZ_PT_BR_FEMININA_NAO_INSTALADA" in proc.stderr:
            raise SpeechError(
                "Não há voz feminina brasileira compatível com Windows SAPI instalada."
            )
        raise SpeechError(
            f"Windows SAPI falhou (código {proc.returncode}). "
            "Tente Dora (local)."
        )

    prefix = "ANGELA_VOICE="
    selected = next(
        (line[len(prefix):].strip() for line in proc.stdout.splitlines()
         if line.startswith(prefix)), None,
    )
    if not selected:
        raise SpeechError("O Windows não confirmou o nome da voz.")
    return f"{selected} (português brasileiro, offline)"


def _friendly_error(provider: str, exc: Exception) -> str:
    """Erros sem URLs assinadas, chaves ou tokens na interface."""
    if provider == "edge":
        if isinstance(exc, SpeechError):
            return f"Francisca: {exc}"
        return f"Francisca: falha de reprodução ({type(exc).__name__})."
    if provider == "windows":
        if isinstance(exc, SpeechError):
            return f"Windows: {exc}"
        return f"Windows: falha de reprodução ({type(exc).__name__})."
    if isinstance(exc, (SpeechError, RuntimeError)):
        return f"Dora: {str(exc)[:240]}"
    return f"Dora: falha de síntese ({type(exc).__name__})."


def speak(text: str, provider: str = "auto") -> str:
    """Voz Dora local em primeiro lugar; alternativas explícitas e diagnóstico."""
    if provider not in {"auto", "kokoro", "edge", "windows"}:
        raise ValueError("Provedor de voz inválido.")
    text = text.strip()
    if not text:
        return "Nenhum texto informado."
    with _SPEAK_LOCK:
        errors = []
        order = ("kokoro", "windows", "edge") if provider == "auto" else (provider,)
        for current in order:
            try:
                if current == "kokoro":
                    return _speak_kokoro(text[:1800])
                if current == "windows":
                    return _speak_windows(text[:1800])
                return _speak_edge(text[:1800])
            except Exception as exc:
                errors.append(_friendly_error(current, exc))

    raise SpeechError(
        "Não consegui falar. " + " | ".join(errors) +
        " | Confira a saída de som e teste Dora (local)."
    )
