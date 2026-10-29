"""Métricas opt-in de latência sem transcrição, áudio, imagens ou segredos.

Nenhuma dependência externa e nenhum upload. Um único evento compactado
é gravado no audit_log local apenas quando ANGELA_PERF_DIAGNOSTICS=1.
"""
from __future__ import annotations

from contextlib import contextmanager
import os
import time

ALLOWED_PHASES = frozenset({
    "wake_to_command", "command_dispatch", "intent_routing", "ai_request",
    "ai_first_response", "ai_total", "windows_action", "tts_synthesis",
    "tts_first_audio", "tts_total", "camera_capture", "screen_capture",
    "visual_analysis", "voice_end_to_audio", "microphone_probe",
})


def enabled() -> bool:
    return os.environ.get("ANGELA_PERF_DIAGNOSTICS", "0") == "1"


def measure_ms(start_ns: int, end_ns: int | None = None) -> float:
    end = time.perf_counter_ns() if end_ns is None else end_ns
    return round(max(0, end - start_ns) / 1_000_000, 3)


def metric(phase: str, duration_ms: float, *, status: str = "ok") -> None:
    if not enabled() or phase not in ALLOWED_PHASES:
        return
    try:
        value = float(duration_ms)
        if value < 0 or value > 120_000:
            return
        from .audit_log import record
        record(
            "perf_metric", phase=phase,
            duration_ms=round(value, 3),
            status=status if status in {"ok", "error", "timeout", "cancelled"} else "error",
        )
    except (TypeError, ValueError, OSError):
        return


@contextmanager
def timed(phase: str):
    start = time.perf_counter_ns()
    try:
        yield
    except Exception:
        metric(phase, measure_ms(start), status="error")
        raise
    else:
        metric(phase, measure_ms(start))
