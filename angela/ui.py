"""Janela de testes do protótipo Ângela AI no Windows."""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import scrolledtext

from .assistant import AssistantEngine
from .speech import VOICE_TEST_SENTENCE
from .wake import WakeListener


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
        root.title("Ângela AI — v0.5")
        root.geometry("780x630")
        root.minsize(590, 510)
        root.configure(bg=self.BACKGROUND)
        self.engine = AssistantEngine()
        self.events: queue.Queue[tuple[str, str]] = queue.Queue()
        self.wake_listener = WakeListener(lambda kind, value: self.events.put((kind, value)))
        self.wake_enabled = tk.BooleanVar(value=False)
        self.busy = False
        self.voice_enabled = tk.BooleanVar(value=True)
        self.voice_provider = tk.StringVar(value="Dora (local)")
        self.status = tk.StringVar(value="Pronta para conversar")

        title = tk.Label(
            root, text="ÂNGELA  /  AI", fg=self.TEXT, bg=self.BACKGROUND,
            font=("Segoe UI", 21, "bold"), anchor="w",
        )
        title.pack(fill="x", padx=22, pady=(20, 0))
        caption = tk.Label(
            root, text="Assistente pessoal Windows  •  Protótipo 0.5",
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

        wake_row = tk.Frame(root, bg=self.BACKGROUND)
        wake_row.pack(fill="x", padx=22, pady=(2, 3))
        tk.Checkbutton(
            wake_row, text="Ativar escuta por 'Ângela' (microfone contínuo)",
            variable=self.wake_enabled, command=self.on_toggle_wake,
            bg=self.BACKGROUND, fg=self.SUBTLE, selectcolor=self.SURFACE,
            activebackground=self.BACKGROUND, activeforeground=self.TEXT,
            font=("Segoe UI", 10),
        ).pack(side="left")

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
            "Agora também procuro aplicativos instalados, abro pastas dos SSDs e posso solicitar o fechamento de janelas com confirmação. Dora continua sendo a voz padrão.",
        )
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(100, self.process_events)
        self.entry.focus_set()

    def add_message(self, sender: str, content: str) -> None:
        self.messages.configure(state="normal")
        tag = "user" if sender.startswith("Você") else "assistant"
        self.messages.insert("end", f"{sender}\n", tag)
        self.messages.insert("end", f"{content}\n\n")
        self.messages.configure(state="disabled")
        self.messages.see("end")

    def set_busy(self, state: bool, status: str = "") -> None:
        self.busy = state
        button_state = "disabled" if state else "normal"
        for button in (self.send_button, self.listen_button, self.test_voice_button):
            button.configure(state=button_state)
        self.status.set(status if state else self.idle_status())

    def idle_status(self) -> str:
        return "Escutando: diga 'Ângela'" if self.wake_enabled.get() else "Pronta para conversar"

    def on_toggle_wake(self) -> None:
        if self.wake_enabled.get():
            if self.busy:
                self.wake_enabled.set(False)
                self.add_message("Ângela", "Espere minha resposta terminar antes de ativar a escuta.")
                return
            if self.wake_listener.start():
                self.status.set("Iniciando microfone contínuo...")
            else:
                self.wake_listener.resume()
                self.status.set(self.idle_status())
        else:
            self.wake_listener.stop()
            self.status.set(self.idle_status())

    def restore_wake(self, follow_up: bool = False) -> None:
        if not self.wake_enabled.get() or self.busy:
            return
        if self.wake_listener.running:
            self.wake_listener.resume(follow_up=follow_up)
        else:
            self.wake_listener.start()
        self.status.set("Aguardando comando (10 s)..." if follow_up else self.idle_status())

    def begin_request(self, message: str) -> None:
        if self.wake_listener.running:
            self.wake_listener.pause()
        self.set_busy(True, "Processando...")
        threading.Thread(target=self.reply_worker, args=(message,), daemon=True).start()

    def on_close(self) -> None:
        self.wake_enabled.set(False)
        self.wake_listener.stop()
        self.root.destroy()

    def on_send(self, event=None) -> None:
        if self.busy:
            return
        message = self.entry.get().strip()
        if not message:
            return
        self.entry.delete(0, "end")
        self.add_message("Você", message)
        self.begin_request(message)

    def reply_worker(self, message: str) -> None:
        try:
            answer = self.engine.reply(message)
        except Exception as exc:
            answer = f"Ocorreu um erro inesperado: {type(exc).__name__}."
        self.events.put(("answer", answer))

    def on_listen(self) -> None:
        if self.busy:
            return
        if self.wake_listener.running:
            self.wake_listener.stop()
            if self.wake_listener.running:
                self.add_message("Ângela", "Aguarde a liberação do microfone.")
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
        if self.wake_listener.running:
            self.wake_listener.pause()
        self.set_busy(True, "Testando a saída de voz...")
        provider = self.selected_provider()
        threading.Thread(
            target=self.voice_worker,
            args=(VOICE_TEST_SENTENCE, provider, True),
            daemon=True,
        ).start()

    def voice_worker(self, text: str, provider: str, test: bool = False, ack: bool = False) -> None:
        try:
            from .speech import speak
            used_voice = speak(text, provider=provider)
            self.events.put(("voice_ack_ok" if ack else "voice_test_ok" if test else "voice_ok", used_voice))
        except Exception as exc:
            self.events.put(("voice_ack_error" if ack else "voice_test_error" if test else "voice_error", str(exc)))

    def process_events(self) -> None:
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == "answer":
                    self.add_message("Ângela", data)
                    if self.voice_enabled.get():
                        self.status.set("Ângela falando...")
                        threading.Thread(
                            target=self.voice_worker,
                            args=(data, self.selected_provider()),
                            daemon=True,
                        ).start()
                    else:
                        self.set_busy(False)
                        self.restore_wake()
                elif kind == "heard":
                    self.set_busy(False)
                    if data:
                        self.add_message("Você (voz)", data)
                        self.begin_request(data)
                    else:
                        self.status.set("Nenhuma fala compreendida.")
                        self.restore_wake()
                elif kind == "error":
                    self.add_message("Ângela", data)
                    self.set_busy(False)
                    self.restore_wake()
                elif kind == "wake_ready":
                    if self.wake_enabled.get() and not self.busy:
                        self.status.set(self.idle_status())
                elif kind == "wake_activated":
                    if not self.wake_enabled.get() or self.busy:
                        continue
                    self.wake_listener.pause()
                    self.add_message("Ângela", "Oi! Estou ouvindo.")
                    if self.voice_enabled.get():
                        self.set_busy(True, "Ângela respondendo...")
                        threading.Thread(
                            target=self.voice_worker,
                            args=("Oi! Estou ouvindo.", self.selected_provider(), False, True),
                            daemon=True,
                        ).start()
                    else:
                        self.restore_wake(follow_up=True)
                elif kind == "wake_command":
                    if not self.wake_enabled.get() or self.busy:
                        continue
                    self.add_message("Você (voz)", data)
                    self.begin_request(data)
                elif kind == "wake_timeout":
                    if self.wake_enabled.get() and not self.busy:
                        self.status.set(self.idle_status())
                elif kind == "wake_error":
                    if self.wake_enabled.get():
                        self.wake_enabled.set(False)
                        self.wake_listener.stop()
                        self.add_message("Ângela", data)
                        self.status.set("Escuta desativada: confira o microfone.")
                elif kind in ("voice_ack_ok", "voice_ack_error"):
                    if kind == "voice_ack_error":
                        self.add_message("Ângela", f"Falha de voz: {data}")
                    self.set_busy(False)
                    self.restore_wake(follow_up=True)
                elif kind == "voice_ok":
                    self.set_busy(False)
                    self.restore_wake()
                elif kind == "voice_test_ok":
                    self.add_message(
                        "Ângela", f"Teste concluído com: {data}. "
                        "Se não ouviu, confira a saída de som do Windows.",
                    )
                    self.set_busy(False)
                    self.restore_wake()
                elif kind in {"voice_error", "voice_test_error"}:
                    self.add_message("Ângela", f"Falha na saída de voz: {data}")
                    self.set_busy(False)
                    self.restore_wake()
                # wake_stopped é apenas informativo.
        except queue.Empty:
            pass
        self.root.after(100, self.process_events)


def main() -> None:
    root = tk.Tk()
    AngelaWindow(root)
    root.mainloop()
