"""Histórico local, feedback e exportação para diagnóstico; sem executar ações."""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import json
from pathlib import Path
import threading

from .audit_log import record, _safe

ROOT = Path.home() / "AppData" / "Local" / "AngelaAI"
DEFAULT_PATH = ROOT / "feedback.jsonl"
CONVERSATION_PATH = ROOT / "conversation.jsonl"
_LOCK = threading.RLock()


def _write_line(path: Path, data: dict, max_bytes=500_000):
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(_safe(data), ensure_ascii=False) + "\n"
    with _LOCK:
        if path.exists() and path.stat().st_size + len(line.encode("utf-8")) > max_bytes:
            backup = path.with_suffix(path.suffix + ".old")
            path.replace(backup)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)


def save_feedback(command: str, reply: str, accepted: bool,
                  path: Path | None = None) -> None:
    target = Path(path) if path else DEFAULT_PATH
    entry = {
        "at": datetime.now(timezone.utc).isoformat(),
        "command": str(command)[:1500],
        "reply": str(reply)[:1500],
        "accepted": bool(accepted),
    }
    _write_line(target, entry)
    record("user_execution_feedback", accepted=bool(accepted), command=command[:300])


def record_conversation(role: str, text: str, path: Path | None = None) -> None:
    if role not in {"user", "assistant"}:
        raise ValueError("Papel desconhecido")
    _write_line(
        Path(path) if path else CONVERSATION_PATH,
        {"at": datetime.now(timezone.utc).isoformat(),
         "role": role, "text": str(text)[:1500]},
    )


def _read_recent(path: Path, limit: int) -> list[dict]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as handle:
            lines = deque(handle, maxlen=max(1, min(limit, 200)))
        result = []
        for line in lines:
            try:
                entry = json.loads(line)
                if isinstance(entry, dict):
                    result.append(entry)
            except ValueError:
                continue
        return result
    except OSError:
        return []


def recent_conversation(limit: int = 20, path: Path | None = None) -> list[dict]:
    return _read_recent(Path(path) if path else CONVERSATION_PATH, limit)


def export_report(report_dir: Path | None = None,
                  feedback_path: Path | None = None,
                  conversation_path: Path | None = None) -> Path:
    directory = Path(report_dir) if report_dir else ROOT / "reports"
    directory.mkdir(parents=True, exist_ok=True)
    filename = "angela_diagnostico_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".txt"
    output = directory / filename
    lines = ["RELATÓRIO LOCAL DE DIAGNÓSTICO — ÂNGELA",
             "Data: " + datetime.now().isoformat(timespec="seconds"),
             "Gerado manualmente. Revise informações pessoais antes de compartilhar.",
             "", "HISTÓRICO RECENTE", ""]
    history = recent_conversation(35, conversation_path)
    if not history:
        lines.append("Nenhuma conversa registrada.")
    for entry in history:
        speaker = "VOCÊ" if entry.get("role") == "user" else "ÂNGELA"
        lines.append(f"[{entry.get('at', '')}] {speaker}: {entry.get('text', '')}")
    lines.extend(["", "AVALIAÇÕES RECENTES", ""])
    recent = _read_recent(Path(feedback_path) if feedback_path else DEFAULT_PATH, 35)
    if not recent:
        lines.append("Nenhuma avaliação registrada.")
    for entry in recent:
        accepted = "SIM" if entry.get("accepted") else "NÃO"
        lines.extend([
            f"[{entry.get('at', '')}] Feedback: {accepted}",
            "Pedido: " + str(entry.get("command", "")),
            "Resposta: " + str(entry.get("reply", "")),
            "",
        ])
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    record("feedback_report_exported", file_name=output.name)
    return output
