"""Janela desktop simples para começar testes no Windows sem Flutter."""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import scrolledtext

from .assistant import AssistantEngine


class AngelaWindow:
    BACKGROUND = "#0b1120"
    SURFACE = "#151f33"
    TEXT = "#edf3ff"
    SUBTLE = "#9bb0cd"
    ACCENT = "#7c9dff"

    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Ângela AI — v0.1")
        root.geometry("740x560")
        root.minsize(540, 440)
        root.configure(bg=self.BACKGROUND)
        self.engine = AssistantEngine()
        self.events: queue.Queue[tuple[str, str]] = queue.Queue()
        self.busy = False
        self.voice_enabled = tk.BooleanVar(value=True)
        self.status = tk.StringVar(value="Pronta para conversar")

        title = tk.Label(
            root, text="ÂNGELA  /  AI", fg=self.TEXT, bg=self.BACKGROUND,
            font=("Segoe UI", 21, "bold"), anchor="w",
        )
        title.pack(fill="x", padx=22, pady=(20, 0))
        caption = tk.Label(
            root, text="Assistente pessoal Windows  •  Protótipo 0.1",
            fg=self.SUBTLE, bg=self.BACKGROUND, font=("Segoe UI", 10),
            anchor="w",
        )
        caption.pack(fill="x", padx=23, pady=(0, 15))

        self.messages = scrolledtext.ScrolledText(
            root, wrap=tk.WORD, bg=self.SURFACE, fg=self.TEXT,
            insertbackground=self.TEXT, selectbackground="#334c77",
            font=("Segoe UI", 11), relief="flat", borderwidth=0, padx=16, pady=14,
            state="disabled",
        )
        self.messages.pack(fill="both", expand=True, padx=22, pady=4)
        self.messages.tag_configure("user", foreground="#a6baff", spacing1=8)
        self.messages.tag_configure("assistant", foreground=self.TEXT, spacing1=8)

        controls = tk.Frame(root, bg=self.BACKGROUND)
        controls.pack(fill="x", padx=22, pady=(12, 5))
        self.entry = tk.Entry(
            controls, bg=self.SURFACE, fg=self.TEXT, insertbackground=self.TEXT,
            font=("Segoe UI", 11), relief="flat", borderwidth=0,
        )
        self.entry.pack(side="left", fill="x", expand=True, ipady=11)
        self.entry.bind("<Return>", self.on_send)

        self.send_button = tk.Button(
            controls, text="Enviar", command=self.on_send,
            bg=self.ACCENT, fg="#0b1120", activebackground="#b3c4ff",
            relief="flat", padx=15, cursor="hand2",
        )
        self.send_button.pack(side="left", padx=(9, 0), ipady=7)
        self.listen_button = tk.Button(
            controls, text="Ouvir (8 s)", command=self.on_listen,
            bg="#263859", fg=self.TEXT, activebackground="#3a537d",
            relief="flat", padx=12, cursor="hand2",
        )
        self.listen_button.pack(side="left", padx=(8, 0), ipady=7)

        footer = tk.Frame(root, bg=self.BACKGROUND)
        footer.pack(fill="x", padx=22, pady=(4, 16))
        tk.Checkbutton(
            footer, text="Ler respostas em voz alta", variable=self.voice_enabled,
            bg=self.BACKGROUND, fg=self.SUBTLE, selectcolor=self.SURFACE,
            activebackground=self.BACKGROUND, activeforeground=self.TEXT,
            font=("Segoe UI", 9),
        ).pack(side="left")
        tk.Label(
            footer, textvariable=self.status, fg=self.SUBTLE,
            bg=self.BACKGROUND, font=("Segoe UI", 9),
        ).pack(side="right")

        self.add_message("Ângela", "Olá! Digite 'ajuda' para conhecer os comandos.")
        self.root.after(100, self.process_events)
        self.entry.focus_set()

    def add_message(self, sender: str, content: str) -> None:
        self.messages.configure(state="normal")
        tag = "user" if sender == "Você" else "assistant"
        self.messages.insert("end", f"{sender}\n", tag)
        self.messages.insert("end", f"{content}\n\n")
        self.messages.configure(state="disabled")
        self.messages.see("end")

    def set_busy(self, state: bool, status: str = "") -> None:
        self.busy = state
        self.send_button.configure(state="disabled" if state else "normal")
        self.listen_button.configure(state="disabled" if state else "normal")
        self.status.set(status if state else "Pronta para conversar")

    def on_send(self, event=None) -> None:
        if self.busy:
            return
        message = self.entry.get().strip()
        if not message:
            return
        self.entry.delete(0, "end")
        self.add_message("Você", message)
        self.set_busy(True, "Processando...")
        threading.Thread(target=self.reply_worker, args=(message,), daemon=True).start()

    def reply_worker(self, message: str) -> None:
        try:
            answer = self.engine.reply(message)
        except Exception as exc:
            answer = f"Ocorreu um erro inesperado: {type(exc).__name__}."
        self.events.put(("answer", answer))

    def on_listen(self) -> None:
        if self.busy:
            return
        self.set_busy(True, "Escutando por até 8 segundos...")
        threading.Thread(target=self.listen_worker, daemon=True).start()

    def listen_worker(self) -> None:
        try:
            from .speech import listen_once
            transcription = listen_once()
            self.events.put(("heard", transcription))
        except Exception as exc:
            self.events.put(("error", f"Não foi possível usar o microfone: {exc}"))

    def voice_worker(self, text: str) -> None:
        try:
            from .speech import speak
            speak(text)
        except Exception as exc:
            self.events.put(("voice_error", f"Voz indisponível: {type(exc).__name__}."))

    def process_events(self) -> None:
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == "answer":
                    self.add_message("Ângela", data)
                    self.set_busy(False)
                    if self.voice_enabled.get():
                        threading.Thread(
                            target=self.voice_worker, args=(data,), daemon=True
                        ).start()
                elif kind == "heard":
                    self.set_busy(False)
                    if data:
                        self.entry.insert(0, data)
                        self.on_send()
                    else:
                        self.status.set("Nenhuma fala compreendida. Tente novamente.")
                elif kind == "error":
                    self.set_busy(False)
                    self.add_message("Ângela", data)
                elif kind == "voice_error":
                    self.status.set(data)
        except queue.Empty:
            pass
        self.root.after(100, self.process_events)


def main() -> None:
    root = tk.Tk()
    AngelaWindow(root)
    root.mainloop()
