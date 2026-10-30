"""Medição segura de primeira resposta e conclusão da IA em rede.

Usa somente uma frase fixa de teste; nunca envia histórico, perfil,
imagem ou texto dito ao microfone. Não imprime chaves nem respostas.
"""
from __future__ import annotations

import json
import os
from statistics import mean, median
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from angela.chat import API_URL, DEFAULT_MODEL, select_model


def main():
    load_dotenv()
    secret = os.environ.get("GROQ_API_KEY", "").strip()
    if not secret:
        print("GROQ_NOT_CONFIGURED")
        return
    model = select_model(os.environ.get("GROQ_MODEL", DEFAULT_MODEL))
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "Responda somente: OK."}],
        "temperature": 0,
        "max_completion_tokens": 128,
        "stream": True,
    }).encode("utf-8")
    vals_first, vals_total = [], []
    for i in range(3):
        started = perf_counter()
        first = None
        try:
            request = Request(API_URL, method="POST", data=payload, headers={
                "Authorization": "Bearer " + secret,
                "Content-Type": "application/json",
                "User-Agent": "Angela-IA-PerformanceTest/1.0",
            })
            with urlopen(request, timeout=18) as connection:
                for raw in connection:
                    line = raw.strip()
                    if not line.startswith(b"data:"):
                        continue
                    if line == b"data: [DONE]":
                        break
                    try:
                        event = json.loads(line[5:])
                    except ValueError:
                        continue
                    choice = (event.get("choices") or [{}])[0]
                    content = (choice.get("delta") or {}).get("content")
                    if content and first is None:
                        first = 1000 * (perf_counter() - started)
            duration = 1000 * (perf_counter() - started)
            print("SAMPLE", i+1, "status", "ok",
                  "first_text_ms", round(first, 1) if first is not None else "none",
                  "total_ms", round(duration, 1), flush=True)
            vals_total.append(duration)
            if first is not None:
                vals_first.append(first)
        except HTTPError as exc:
            print("SAMPLE", i+1, "http_status", exc.code, flush=True)
        except (URLError, TimeoutError) as exc:
            print("SAMPLE", i+1, "network_error", type(exc).__name__, flush=True)
    for label, values in (("first_text", vals_first), ("total", vals_total)):
        if values:
            print("SUMMARY", label, "n", len(values),
                  "p50_ms", round(median(values), 1),
                  "mean_ms", round(mean(values), 1),
                  "p95_ms", round(sorted(values)[min(len(values)-1, int(.95*len(values)))], 1),
                  flush=True)


if __name__ == "__main__":
    main()
