"""HUD original inspirado em interfaces holográficas de ficção científica."""
from __future__ import annotations

import math
import tkinter as tk


class AngelaHUD(tk.Canvas):
    """Núcleo animado que acompanha os estados da assistente."""

    COLORS = {
        "idle": "#3acfe8",
        "listening": "#43f0bd",
        "processing": "#ffcb75",
        "speaking": "#a7a2ff",
    }

    def __init__(self, master, *, state_provider=None, **kwargs):
        kwargs.setdefault("height", 205)
        kwargs.setdefault("background", "#07111f")
        kwargs.setdefault("highlightthickness", 0)
        super().__init__(master, **kwargs)
        self.state_provider = state_provider or (lambda: "idle")
        self.phase = 0.0
        self._running = True
        self.bind("<Destroy>", self._on_destroy)
        self.after(60, self.animate)

    def _on_destroy(self, event):
        if event.widget is self:
            self._running = False

    def animate(self):
        if not self._running:
            return
        self.phase += 0.07
        self.delete("all")
        width = max(self.winfo_width(), 300)
        height = max(self.winfo_height(), 180)
        cx, cy = width / 2, height / 2
        state = self.state_provider()
        if state not in self.COLORS:
            state = "idle"
        accent = self.COLORS[state]
        radius = min(height * 0.40, 85)
        pulse = 2.5 * math.sin(self.phase * 2)

        # Grade discreta do painel.
        for x in range(0, width, 28):
            self.create_line(x, 0, x, height, fill="#10253a")
        for y in range(0, height, 28):
            self.create_line(0, y, width, y, fill="#10253a")

        for scale, color, thickness in (
            (1.10, "#194961", 1),
            (0.94, accent, 2),
            (0.77, "#255b74", 2),
            (0.54, accent, 1),
        ):
            r = radius * scale + pulse
            self.create_oval(cx-r, cy-r, cx+r, cy+r, outline=color, width=thickness)

        # Segmentos orbitais lembram um radar digital.
        for index in range(12):
            angle = (index * 30 + self.phase * 30) % 360
            r = radius * 0.94 + pulse
            box = (cx-r, cy-r, cx+r, cy+r)
            self.create_arc(*box, start=angle, extent=13, style="arc",
                            outline=accent, width=3)
        for index in range(8):
            angle = index * math.pi / 4 - self.phase / 2
            inner, outer = radius * .59, radius * .72
            self.create_line(
                cx + inner * math.cos(angle), cy + inner * math.sin(angle),
                cx + outer * math.cos(angle), cy + outer * math.sin(angle),
                fill="#4a8ea4", width=2,
            )

        self.create_text(cx, cy - 9, text="Â", font=("Segoe UI", 30, "bold"),
                         fill="#e8fbff")
        self.create_text(cx, cy + 22, text="ANGELA AI", font=("Segoe UI", 9, "bold"),
                         fill=accent)
        self.create_text(16, 16, anchor="nw", text="RHBM // ASSISTANT",
                         font=("Consolas", 9), fill="#6bafc6")
        self.create_text(width - 16, height - 16, anchor="se",
                         text={"idle": "EM ESPERA", "listening": "OUVINDO",
                               "processing": "PROCESSANDO", "speaking": "RESPONDENDO"}[state],
                         font=("Consolas", 9, "bold"), fill=accent)
        self.after(60, self.animate)
