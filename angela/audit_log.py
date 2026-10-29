"""Persistent local, bounded JSONL audit trail for Angela actions."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
import re
import threading
import uuid

_LOCK = threading.RLock()
_LOCAL = threading.local()
MAX_BYTES = 3_000_000
MAX_BACKUPS = 4
_SECRET = re.compile(r"(?i)(api[_ -]?key|token|password|senha|secret|authorization|bearer)\s*[:=]\s*[^\s,;]+")
_URL_SECRET = re.compile(r"(?i)([?&](?:key|token|secret|password|access_token)=)[^&\s]+")


def log_path() -> Path:
    override = os.environ.get("ANGELA_AUDIT_PATH")
    return Path(override) if override else Path.home() / "AppData" / "Local" / "AngelaAI" / "logs" / "history.jsonl"


def begin_interaction() -> str:
    trace_id = uuid.uuid4().hex[:16]
    _LOCAL.trace_id = trace_id
    return trace_id


def set_interaction(trace_id: str | None) -> None:
    _LOCAL.trace_id = trace_id


def _safe(value):
    if isinstance(value, str):
        return _URL_SECRET.sub(r"\1[REDACTED]", _SECRET.sub(r"\1=[REDACTED]", value))[:4000]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if isinstance(value, (tuple, list)):
        return [_safe(v) for v in value[:30]]
    if isinstance(value, dict):
        return {str(k): ("[REDACTED]" if re.search("(?i)token|secret|password|senha|api.key", str(k)) else _safe(v)) for k, v in list(value.items())[:30]}
    return _safe(str(value))


def record(event: str, **details) -> None:
    """Never let audit logging break voice or operating system actions."""
    try:
        data = {"at": datetime.now(timezone.utc).isoformat(), "event": event,
                "trace_id": getattr(_LOCAL, "trace_id", None), "data": _safe(details)}
        line = json.dumps(data, ensure_ascii=False) + "\n"
        with _LOCK:
            path = log_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.is_file() and path.stat().st_size + len(line.encode("utf-8")) > MAX_BYTES:
                for i in range(MAX_BACKUPS, 0, -1):
                    current = path.with_name(path.name + f".{i}")
                    if i == MAX_BACKUPS and current.exists():
                        current.unlink()
                    elif current.exists():
                        current.rename(path.with_name(path.name + f".{i+1}"))
                path.rename(path.with_name(path.name + ".1"))
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line)
    except (OSError, ValueError, TypeError):
        pass
