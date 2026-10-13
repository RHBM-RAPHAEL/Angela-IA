"""Janela de testes do protótipo Ângela AI no Windows."""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import scrolledtext

from .assistant import AssistantEngine
from .speech import VOICE_TEST_SENTENCE


class AngelaWindow:
    BACKGROUND = "#0b1120"
    SURFACE = "#151f33"
    TEXT = "#edf3ff"
    SUBTLE = "#9bb0cd"
    ACCENT = "#7c9dff"

    PROVIDERS = {
        "Automático (Dora → Windows → Francisca)": "auto",
        "Dora (local)": "kokoro",
        "Francisca (online)": "edge",
        "Windows (offline)": "windows",
    }

    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Ângela AI — v0.3")
        root.geometry("760x600")
        root.minsize(580, 480)
        root.configure(bg=self.BACKGROUND)
        self.engine = AssistantEngine()
        self.events: queue.Queue[tuple[str, str]] = queue.Queue()
        self.busy = False
        self.voice_enabled = tk.BooleanVar(value=True)
        self.voice_provider = tk.StringVar(value="Automático (Dora → Windows → Francisca)")
        self.status = tk.StringVar(value="Pronta para conversar")

        title = tk.Label(
            root, text="ÂNGELA  /  AI", fg=self.TEXT, bg=self.BACKGROUND,
            font=("Segoe UI", 21, "bold"), anchor="w",
        )
        title.pack(fill="x", padx=22, pady=(20, 0))
        caption = tk.Label(
            root, text="Assistente pessoal Windows  •  Protótipo 0.3",
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

        voice_controls = tk.Frame(root, bg=self.BACKGROUND)
        voice_controls.pack(fill="x", padx=22, pady=(7, 2))
        tk.Checkbutton(
            voice_controls, text="Ler respostas em voz alta",
            variable=self.voice_enabled,
            bg=self.BACKGROUND, fg=self.SUBTLE, selectcolor=self.SURFACE,
            activebackground=self.BACKGROUND, activeforeground=self.TEXT,
            font=("Segoe UI", 9),
        ).pack(side="left")

        self.test_voice_button = tk.Button(
            voice_controls, text="Testar voz", command=self.on_test_voice,
            bg="#263859", fg=self.TEXT, activebackground="#3a537d",
            relief="flat", padx=12, cursor="hand2",
        )
        self.test_voice_button.pack(side="right")

        provider_row = tk.Frame(root, bg=self.BACKGROUND)
        provider_row.pack(fill="x", padx=22, pady=(2, 12))
        tk.Label(
            provider_row, text="Saída de voz:", fg=self.SUBTLE,
            bg=self.BACKGROUND, font=("Segoe UI", 9),
        ).pack(side="left")
        tk.OptionMenu(
            provider_row, self.voice_provider, *self.PROVIDERS.keys()
        ).pack(side="left", padx=(6, 0))
        tk.Label(
            provider_row, textvariable=self.status, fg=self.SUBTLE,
            bg=self.BACKGROUND, font=("Segoe UI", 9),
        ).pack(side="right")

        self.add_message(
            "Ângela",
            "Olá! Digite 'ajuda' para conhecer os comandos. "
            "Use 'Testar voz' para verificar o áudio. Recomendo Dora (local).",
        )
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
        button_state = "disabled" if state else "normal"
        for button in (self.send_button, self.listen_button, self.test_voice_button):
            button.configure(state=button_state)
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

    def selected_provider(self) -> str:
        return self.PROVIDERS[self.voice_provider.get()]

    def on_test_voice(self) -> None:
        if self.busy:
            return
        self.set_busy(True, "Testando a saída de voz...")
        provider = self.selected_provider()
        threading.Thread(
            target=self.voice_worker,
            args=(VOICE_TEST_SENTENCE, provider, True),
            daemon=True,
        ).start()

    def voice_worker(self, text: str, provider: str, test: bool = False) -> None:
        try:
            from .speech import speak
            used_voice = speak(text, provider=provider)
            self.events.put(("voice_test_ok" if test else "voice_ok", used_voice))
        except Exception as exc:
            self.events.put(("voice_test_error" if test else "voice_error", str(exc)))

    def process_events(self) -> None:
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == "answer":
                    self.add_message("Ângela", data)
                    self.set_busy(False)
                    if self.voice_enabled.get():
                        provider = self.selected_provider()
                        threading.Thread(
                            target=self.voice_worker,
                            args=(data, provider),
                            daemon=True,
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
                elif kind == "voice_ok":
                    self.status.set(f"Voz: {data}")
                elif kind == "voice_test_ok":
                    self.set_busy(False)
                    self.add_message(
                        "Ângela", f"Teste de voz concluído usando: {data}. "
                        "Se você não ouviu, confira o volume e a saída de som do Windows.",
                    )
                elif kind in {"voice_error", "voice_test_error"}:
                    if kind == "voice_test_error":
                        self.set_busy(False)
                    self.add_message("Ângela", f"Falha na saída de voz: {data}")
                    self.status.set("Falha na voz — confira a mensagem acima.")
        except queue.Empty:
            pass
        self.root.after(100, self.process_events)


def main() -> None:
    root = tk.Tk()
    AngelaWindow(root)
    root.mainloop()
