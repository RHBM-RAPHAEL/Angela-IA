"""Voz feminina Dora (pt-BR) via Kokoro ONNX, sem servidor externo."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parents[1] / "models" / "kokoro"
MODEL_FILE = MODEL_DIR / "kokoro-v1.0.int8.onnx"
VOICES_FILE = MODEL_DIR / "voices-v1.0.bin"


def files_available() -> bool:
    """Nunca baixar modelos de forma inesperada durante uma conversa."""
    return MODEL_FILE.is_file() and VOICES_FILE.is_file()


@lru_cache(maxsize=1)
def _engine():
    from kokoro_onnx import Kokoro
    from misaki.espeak import EspeakG2P

    if not files_available():
        raise RuntimeError(
            "Modelo Dora não instalado. Execute "
            r".\.venv\Scripts\python.exe -m angela.download_kokoro"
        )
    # O mesmo mecanismo do exemplo oficial de português do kokoro-onnx.
    synthesizer = Kokoro(str(MODEL_FILE), str(VOICES_FILE))
    phonemizer = EspeakG2P(language="pt-br")
    return synthesizer, phonemizer


def speak_dora(text: str) -> str:
    """Sintetiza e reproduz áudio pela saída padrão; retorno só após reprodução."""
    try:
        import sounddevice as sd
        engine, phonemizer = _engine()
        phonemes, _ = phonemizer(text)
        if not phonemes:
            raise RuntimeError("O texto não gerou fonemas em português.")
        samples, sample_rate = engine.create(
            phonemes, "pf_dora", is_phonemes=True
        )
        if len(samples) == 0:
            raise RuntimeError("A voz Dora não gerou amostras de áudio.")
        sd.play(samples, sample_rate)
        sd.wait()
    except ImportError as exc:
        raise RuntimeError(
            "Instale as dependências opcionais: "
            r".\.venv\Scripts\python.exe -m pip install -r requirements-voice-kokoro.txt"
        ) from exc
    except (OSError, RuntimeError) as exc:
        raise RuntimeError(f"Falha na voz local Dora: {exc}") from exc
    return "Dora (português brasileiro, local)"
