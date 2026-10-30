"""Resumo de latência por etapa, offline. Não exibe conversas nem mídia."""
from __future__ import annotations

import json
import math
import statistics

from .audit_log import log_path
from .perf_metrics import ALLOWED_PHASES


def percentile(values: list[float], quantile: float) -> float:
    values = sorted(values)
    if not values:
        return 0.0
    index = min(len(values) - 1, math.ceil(quantile * len(values)) - 1)
    return round(values[index], 2)


def summarize(path=None, maximum: int = 5000) -> list[dict]:
    filename = path or log_path()
    try:
        # Exibe somente eventos tipados, nunca transcripts ou payloads.
        with open(filename, encoding="utf-8") as source:
            lines = source.readlines()[-max(1, min(maximum, 10_000)):]
    except OSError:
        return []
    phases: dict[str, list[tuple[float, str]]] = {}
    for line in lines:
        try:
            obj = json.loads(line)
            if obj.get("event") != "perf_metric":
                continue
            data = obj.get("data", {})
            phase, value = data.get("phase"), data.get("duration_ms")
            status = data.get("status", "")
            if phase not in ALLOWED_PHASES or status not in {"ok", "error", "timeout", "cancelled"}:
                continue
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                continue
            phases.setdefault(phase, []).append((float(value), status))
        except (TypeError, KeyError, ValueError, AttributeError, json.JSONDecodeError):
            continue
    output = []
    for phase in sorted(phases):
        entries = phases[phase]
        durations = [v for v, _s in entries]
        output.append({
            "phase": phase, "count": len(entries),
            "p50_ms": round(statistics.median(durations), 2),
            "p95_ms": percentile(durations, .95),
            "mean_ms": round(statistics.mean(durations), 2),
            "errors": sum(1 for _v, status in entries if status != "ok"),
        })
    return output


def main() -> None:
    entries = summarize()
    if not entries:
        print("Sem métricas locais. Ative ANGELA_PERF_DIAGNOSTICS=1 para registrar etapas.")
        return
    print(f"{'Etapa':25} {'N':>4} {'p50 ms':>9} {'p95 ms':>9} {'Média':>9} {'Erros':>5}")
    for row in entries:
        print(f"{row['phase']:25} {row['count']:4d} {row['p50_ms']:9.2f} "
              f"{row['p95_ms']:9.2f} {row['mean_ms']:9.2f} {row['errors']:5d}")


if __name__ == "__main__":
    main()
