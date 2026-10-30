"""Benchmark comparável com síntese simulada; NÃO mede Edge TTS real.

Três segmentos de 100 ms cada simulam 300 ms de síntese total.
Compara tempo de primeira reprodução no legado e no pipeline.
"""
from __future__ import annotations

import asyncio
import os
import statistics
import sys
import time
import types

from angela.speech import speak


def percentile(values, q):
    ordered = sorted(values)
    return round(ordered[min(len(ordered)-1, int(q * (len(ordered)-1)))], 2)


starts = []
class FakeCommunicate:
    def __init__(self, text, voice):
        self.text = text

    async def save(self, path):
        await asyncio.sleep(0.30)
        with open(path, "wb") as stream:
            stream.write(b"fake-mp3")

    async def stream(self):
        await asyncio.sleep(0.10)
        yield {"type": "audio", "data": b"fake-mp3"}

fake_edge = types.ModuleType("edge_tts")
fake_edge.Communicate = FakeCommunicate
sys.modules["edge_tts"] = fake_edge

class FakeMusic:
    def load(self, *_args): pass
    def play(self): starts.append(time.perf_counter())
    def set_volume(self, *_args): pass
    def get_busy(self): return False
    def unload(self): pass
    def stop(self): pass

class FakeMixer:
    music = FakeMusic()
    def init(self): pass
    def quit(self): pass

fake_pygame = types.ModuleType("pygame")
fake_pygame.mixer = FakeMixer()
sys.modules["pygame"] = fake_pygame

def samples(streaming, n=12):
    os.environ["ANGELA_TTS_STREAMING"] = "1" if streaming else "0"
    values = []
    text = "Olá. " + "Esta é uma frase de teste com a mesma voz Thalita. " * 5
    for _ in range(n):
        begin_count = len(starts)
        start = time.perf_counter()
        speak(text, on_level=lambda _v: None)
        values.append((starts[begin_count] - start) * 1000)
    return values

if __name__ == "__main__":
    legacy = samples(False)
    fast = samples(True)
    print("SIMULATED_ONLY; network_model=300ms_total; audio_output=mock; n=12")
    for name, data in (("legacy", legacy), ("streaming", fast)):
        print(name, "mean_ms", round(statistics.mean(data),2),
              "p50_ms",round(statistics.median(data),2),
              "p95_ms",percentile(data,.95))
    print("p50_reduction_pct",round(
        (1-statistics.median(fast)/statistics.median(legacy))*100,1
    ))
