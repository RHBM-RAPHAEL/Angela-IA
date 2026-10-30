"""Mede somente geracao de MP3 sintetico com Edge TTS; nenhum audio e tocado.

Nao acessa microfone, webcam, tela, dados privados ou credenciais.
A frase de teste e constante. Mede duracao ate concluir bytes MP3 no servidor.
"""
from __future__ import annotations

import asyncio
from statistics import median, mean
from time import perf_counter

from angela.streaming_tts import split_phrases

VOICE = "pt-BR-ThalitaNeural"
TEXT = (
    "Olá, estou ouvindo. "
    "A previsão do tempo de hoje está disponível para consulta. "
    "Também posso explicar os detalhes na tela e responder suas perguntas. "
    "Diga o que deseja saber."
)


def p95(values):
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, int(len(ordered) * .95))], 1)


async def probe(text: str) -> tuple[float, float, int]:
    import edge_tts
    start = perf_counter()
    first_byte = None
    size = 0
    async def receive():
        nonlocal first_byte, size
        async for item in edge_tts.Communicate(text, VOICE).stream():
            if item.get("type") == "audio":
                if first_byte is None:
                    first_byte = 1000 * (perf_counter() - start)
                size += len(item["data"])
    await asyncio.wait_for(receive(), timeout=19)
    if size <= 0 or first_byte is None:
        raise RuntimeError("No audio returned")
    return round(1000 * (perf_counter() - start), 1), round(first_byte, 1), size


async def main():
    groups = {
        "mp3_completo": TEXT,
        "primeira_frase": split_phrases(TEXT, maximum=100)[0],
    }
    for name, phrase in groups.items():
        results = []
        for i in range(5):
            try:
                total, first, size = await probe(phrase)
                results.append(total)
                print("SAMPLE", name, i + 1, "complete_ms", total,
                      "first_packet_ms", first, "mp3_bytes", size, flush=True)
            except Exception as exc:
                print("ERROR", name, i + 1, type(exc).__name__, flush=True)
        if results:
            print("SUMMARY", name, "n", len(results),
                  "mean_ms", round(mean(results), 1),
                  "p50_ms", round(median(results), 1),
                  "p95_ms", p95(results), flush=True)
        else:
            print("SUMMARY", name, "no_successful_samples", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
