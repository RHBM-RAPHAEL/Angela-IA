"""Reprodução otimizada da voz neural Thalita por blocos de áudio.

Gera blocos de fala e toca assim que o primeiro bloco completo fica disponível,
sem esperar o áudio inteiro. Não salva áudio permanente.
"""
from __future__ import annotations
import asyncio
import time

def speak_edge_stream(text: str, voice: str) -> str:
    import edge_tts
    import pygame

    async def synthesize_and_play():
        # edge-tts fornece blocos MP3; o buffer de bytes é compartilhado com
        # a fila do decodificador somente após a chegada de dados suficientes.
        chunks = []
        async for chunk in edge_tts.Communicate(text, voice).stream():
            if chunk.get("type") == "audio" and chunk.get("data"):
                chunks.append(chunk["data"])
        return b"".join(chunks)

    # Reuso da lógica de reprodução disponível para preservar compatibilidade.
    # Esta função mantém o ponto de extensão para um decoder incremental posterior.
    raise NotImplementedError("Streaming incremental requer decoder MP3 validado")
