"""Stream Edge neural speech as a sequence of independently playable MP3 chunks.

The first sentence plays while subsequent sentences are synthesized. This
reduces perceived latency without changing the selected voice.
"""
from __future__ import annotations

import asyncio
import re
import time


def split_phrases(text: str, maximum: int = 145) -> list[str]:
    text = " ".join(text.split())
    if not text:
        return []
    segments = re.split(r"(?<=[.!?;:])\s+", text)
    result = []
    for segment in segments:
        words = segment.split()
        pending = ""
        for word in words:
            if pending and len(pending) + len(word) + 1 > maximum:
                result.append(pending)
                pending = word
            else:
                pending = (pending + " " + word).strip()
        if pending:
            result.append(pending)
    return result


def synthesize_segments(text: str, voice: str, on_segment):
    """Callback receives complete MP3 segment; no local permanent storage."""
    import edge_tts

    async def produce():
        for i, phrase in enumerate(split_phrases(text)):
            chunks = []
            async for packet in edge_tts.Communicate(phrase, voice).stream():
                if packet.get("type") == "audio":
                    chunks.append(packet["data"])
            if not chunks:
                raise RuntimeError("Speech service returned no audio")
            on_segment(b"".join(chunks), i)
    asyncio.run(produce())
