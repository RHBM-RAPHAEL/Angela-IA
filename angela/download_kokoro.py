"""Baixa os arquivos oficiais da Dora/Kokoro local, fora do Git.

Executar uma vez: python -m angela.download_kokoro
"""
from __future__ import annotations

import os
from pathlib import Path
from urllib.request import Request, urlopen

from .kokoro_local import MODEL_DIR, MODEL_FILE, VOICES_FILE

RELEASE_BASE = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/"
    "model-files-v1.1/"
)
FILES = (
    (MODEL_FILE, RELEASE_BASE + MODEL_FILE.name, 100_000_000),
    (VOICES_FILE, RELEASE_BASE + VOICES_FILE.name, 20_000_000),
)


def install_kokoro() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    for dest, url, minimum_bytes in FILES:
        if dest.is_file() and dest.stat().st_size >= minimum_bytes:
            print(f"Já instalado: {dest.name}")
            continue

        pending = dest.with_name(dest.name + ".part")
        print(f"Baixando {dest.name} — isso pode demorar alguns minutos...")
        try:
            request = Request(url, headers={"User-Agent": "Angela-IA/0.3"})
            with urlopen(request, timeout=120) as source, pending.open("wb") as target:
                total = 0
                progress = 0
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    target.write(chunk)
                    total += len(chunk)
                    if total // (10 * 1024 * 1024) > progress:
                        progress = total // (10 * 1024 * 1024)
                        print(f"  {total // (1024 * 1024)} MB recebidos...", flush=True)
            if pending.stat().st_size < minimum_bytes:
                raise RuntimeError(
                    "Download incompleto. Verifique sua conexão e tente novamente."
                )
            os.replace(pending, dest)
            print(f"Instalado: {dest.name} ({dest.stat().st_size // (1024 * 1024)} MB)")
        finally:
            if pending.exists():
                pending.unlink()

    print("Modelo Dora preparado. Instale também requirements-voice-kokoro.txt.")


if __name__ == "__main__":
    install_kokoro()
