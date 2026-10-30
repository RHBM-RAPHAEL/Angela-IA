"""Edge TTS em segmentos com prefetch controlado; sem gravação em disco.

O produtor recebe frases do Edge em uma thread daemon e o consumidor pode
começar a tocar a primeira enquanto as próximas são sintetizadas.
"""
from __future__ import annotations

import asyncio
import queue
import re
import threading
from typing import Callable, Iterator


def split_phrases(text: str, maximum: int = 100) -> list[str]:
    text = " ".join(text.split())
    if not text:
        return []
    result: list[str] = []
    for segment in re.split(r"(?<=[.!?;:])\s+", text):
        pending = ""
        for word in segment.split():
            if pending and len(pending) + len(word) + 1 > maximum:
                result.append(pending)
                pending = word
            else:
                pending = (pending + " " + word).strip()
        if pending:
            result.append(pending)
    return result


def synthesize_segments(text: str, voice: str, on_segment: Callable[[bytes, int], None]):
    """Solicita cada MP3 ao Edge; nenhuma gravação persistente."""
    import edge_tts

    async def produce():
        for i, phrase in enumerate(split_phrases(text)):
            chunks = []
            async for packet in edge_tts.Communicate(phrase, voice).stream():
                if packet.get("type") == "audio":
                    chunks.append(packet["data"])
            if not chunks:
                raise RuntimeError("Serviço de voz não retornou áudio.")
            on_segment(b"".join(chunks), i)
    asyncio.run(produce())


def buffered_segments(text: str, voice: str, *,
                      synthesis=synthesize_segments,
                      max_wait: float = 20.0) -> Iterator[tuple[int, bytes]]:
    """Prefetch de dois MP3: recebe rede sem bloquear a reprodução atual.

    Ao cancelar, não deixa fila ilimitada, e nunca compartilha segredos.
    """
    if not split_phrases(text):
        return
    ready: queue.Queue = queue.Queue(maxsize=2)
    cancelled = threading.Event()
    errors: list[str] = []
    complete = object()

    def enqueue(value):
        while not cancelled.is_set():
            try:
                ready.put(value, timeout=0.1)
                return
            except queue.Full:
                continue

    def produce():
        try:
            synthesis(text, voice, lambda data, index: enqueue((index, data)))
        except Exception as exc:
            errors.append(type(exc).__name__)
        finally:
            enqueue(complete)

    worker = threading.Thread(target=produce, daemon=True, name="AngelaEdgeTTSProducer")
    worker.start()
    try:
        while True:
            try:
                item = ready.get(timeout=max_wait)
            except queue.Empty:
                raise TimeoutError("A síntese da próxima frase excedeu o limite.") from None
            if item is complete:
                if errors:
                    raise RuntimeError("Falha ao sintetizar voz por segmentos: " + errors[0])
                return
            index, audio = item
            if not isinstance(audio, bytes) or not audio:
                raise RuntimeError("Segmento de áudio inválido.")
            yield index, audio
    finally:
        cancelled.set()
        worker.join(timeout=0.15)
