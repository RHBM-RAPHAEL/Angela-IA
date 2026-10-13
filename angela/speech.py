"""Entrada de microfone local e saída de voz com diagnóstico e fallback.

Edge TTS: voz feminina Francisca, português brasileiro, requer serviço online.
Windows: opção offline quando existe uma voz feminina pt-BR instalada em SAPI.
"""
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
    """Falha de voz com explicação para a interface."""


@lru_cache(maxsize=1)
def _get_model(model_path: str):
    from vosk import Model
    return Model(model_path)


def listen_once(seconds: float = 8.0) -> str:
    """Escuta apenas sob comando do usuário, sem enviar áudio à nuvem."""
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


def _speak_edge(text: str) -> str:
    """Gera MP3 Francisca pelo serviço Edge e reproduz via dispositivo padrão."""
    import edge_tts
    import pygame

    with tempfile.TemporaryDirectory(prefix="angela_voice_") as temp_dir:
        output = Path(temp_dir) / "fala.mp3"
        asyncio.run(edge_tts.Communicate(text, _VOICE).save(str(output)))
        if not output.exists() or output.stat().st_size == 0:
            raise SpeechError("O serviço de voz não retornou áudio.")

        initialized = False
        loaded = False
        try:
            pygame.mixer.init()
            initialized = True
            pygame.mixer.music.load(str(output))
            loaded = True
            pygame.mixer.music.set_volume(1.0)
            pygame.mixer.music.play()
            # Não declarar sucesso antes de a reprodução ser processada.
            while pygame.mixer.music.get_busy():
                time.sleep(0.05)
        finally:
            if initialized:
                pygame.mixer.music.stop()
                if loaded:
                    pygame.mixer.music.unload()
                pygame.mixer.quit()
    return "Francisca (português brasileiro, online)"


# Texto vem por variável de ambiente codificada; nunca é interpolado como script.
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
    """Fala local por Windows PowerShell + System.Speech (sem pip extra)."""
    if sys.platform != "win32":
        raise SpeechError("A voz offline desta versão funciona somente no Windows.")

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
        raise SpeechError("PowerShell não está disponível neste Windows.") from exc
    except subprocess.TimeoutExpired as exc:
        raise SpeechError("A voz local demorou demais para responder.") from exc

    if proc.returncode != 0:
        if "VOZ_PT_BR_FEMININA_NAO_INSTALADA" in proc.stderr:
            raise SpeechError(
                "Não há voz feminina pt-BR do Windows Speech instalada. "
                "Use a voz online Francisca ou instale uma voz compatível no Windows."
            )
        error = proc.stderr.strip().splitlines()[-1:] or ["Falha desconhecida."]
        raise SpeechError(f"Falha no sintetizador de voz do Windows: {error[0][:180]}")

    prefix = "ANGELA_VOICE="
    selected = next(
        (line[len(prefix):].strip() for line in proc.stdout.splitlines()
         if line.startswith(prefix)), None,
    )
    if not selected:
        raise SpeechError("O Windows não confirmou qual voz foi usada.")
    return f"{selected} (português brasileiro, offline)"


def speak(text: str, provider: str = "auto") -> str:
    """Fala e devolve o nome da voz utilizada.

    provider='auto' tenta primeiro Francisca online e, se falhar, Windows local.
    provider='edge' e 'windows' testam apenas o mecanismo indicado.
    """
    if provider not in {"auto", "edge", "windows"}:
        raise ValueError("Provedor de voz inválido.")
    text = text.strip()
    if not text:
        return "Nenhum texto informado."

    # Evita que duas falas disputem simultaneamente a saída de áudio.
    with _SPEAK_LOCK:
        errors = []
        order = ("edge", "windows") if provider == "auto" else (provider,)
        for current in order:
            try:
                if current == "edge":
                    return _speak_edge(text[:1800])
                return _speak_windows(text[:1800])
            except Exception as exc:
                errors.append(f"{current}: {type(exc).__name__}: {exc}")

    raise SpeechError(
        "Não consegui falar. " + " | ".join(errors) +
        " | Confira a internet, o volume e a saída de som do Windows."
    )
