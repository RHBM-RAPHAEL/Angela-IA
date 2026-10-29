"""Estados explícitos da Ângela: separados da renderização 3D."""
from __future__ import annotations

from enum import Enum


class AngelaState(str, Enum):
    STARTING = "starting"
    READY = "ready"
    SPEAKING = "speaking"
    LISTENING = "listening"
    PROCESSING = "processing"


STATE_COLORS = {
    AngelaState.STARTING: "#ff3030",
    AngelaState.READY: "#2495ff",
    AngelaState.SPEAKING: "#ff9a17",
    AngelaState.LISTENING: "#29f46b",
    AngelaState.PROCESSING: "#ff9a17",
}


class AngelaStateMachine:
    """Impede estados desconhecidos e expõe transições testáveis."""

    def __init__(self) -> None:
        self.state = AngelaState.STARTING

    def transition(self, state: AngelaState | str) -> AngelaState:
        self.state = AngelaState(state)
        return self.state
