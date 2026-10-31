"""HUD passivo no desktop e janela lateral Qt clicável para conversas."""
from __future__ import annotations

import json
import os
import sys

if sys.platform != "win32":
    raise SystemExit("Overlay disponível apenas no Windows.")

from PySide6.QtCore import Qt, QUrl, QTimer
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

from .conversation_panel import ConversationPanel
from .feedback_store import (
    save_feedback, record_conversation, recent_conversation, export_report,
)
from .states import AngelaState, AngelaStateMachine
from .voice_coordinator import VoiceCoordinator
from .camera_preview import CameraPreviewBridge
from .mini_overlay import MiniAngelaOverlay, LOGO_SOURCES
from .actions import normalize
from .audit_log import record


class TransparentPage(QWebEnginePage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBackgroundColor(QColor(0, 0, 0, 0))

    def javaScriptConsoleMessage(self, level, message, line_number, source_id):
        print(f"WEB_CONSOLE {level} {source_id}:{line_number}: {message}", flush=True)


class HologramOverlay(QWebEngineView):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Angela AI · Núcleo Holográfico")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent;")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.Tool
        )
        self.state_machine = AngelaStateMachine()
        # Janela pequena, acima de aplicativos normais (inclusive Opera).
        # Independente do holograma grande, que continua click-through.
        self.mini_overlay = MiniAngelaOverlay()
        self.mini_overlay.set_state(self.state_machine.state)
        self.tray_icon = QSystemTrayIcon(self)
        for icon_path in LOGO_SOURCES:
            if icon_path.exists():
                self.tray_icon.setIcon(QIcon(str(icon_path)))
                break
        self.tray_icon.setToolTip("Ângela AI · Iniciando")
        self.tray_menu = QMenu()
        self.tray_show_action = self.tray_menu.addAction("Mostrar mini-Ângela")
        self.tray_show_action.triggered.connect(self.show_mini_overlay)
        self.tray_menu.addAction("Ocultar mini-Ângela", self.mini_overlay.hide)
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon.show()
        self.voice_coordinator = None
        self.camera_bridge = CameraPreviewBridge(
            self, status_callback=self.set_camera_status
        )
        self.feedback_candidate = ("", "")
        self.pending_confirmation_command = None
        self.result_windows = {}
        self._next_result_id = 0
        self.voice_timer = QTimer(self)
        self.voice_timer.timeout.connect(self._poll_voice)
        self.setPage(TransparentPage(self))
        self.loadFinished.connect(self._diagnose_load)
        self.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
        )
        # A janela transparente nao deve parecer um aplicativo em tela cheia:
        # isso pode acionar automaticamente o modo Nao incomodar do Windows.
        # Dois pixels fora da borda nao afetam o holograma visivelmente.
        self.setGeometry(QApplication.primaryScreen().geometry().adjusted(0, 0, -2, -2))

        # A esfera não recebe cliques, mas a janela lateral é interativa.
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.chat_panel = ConversationPanel()
        self.chat_panel.feedback_selected.connect(self.on_button_feedback)
        self.chat_panel.export_requested.connect(self.export_feedback_report)
        self.chat_panel.stop_requested.connect(self.close)
        for entry in recent_conversation(18):
            self.chat_panel.add_message(
                "user" if entry.get("role") == "user" else "assistant",
                str(entry.get("text", "")),
            )
        self.load(QUrl("http://127.0.0.1:18766/?v=etapa1-chat"))

    def _diagnose_load(self, ok):
        print("PAGE_LOADED", ok, flush=True)
        if ok:
            self.set_state(AngelaState.STARTING)
            if os.environ.get("ANGELA_ENABLE_VOICE", "") != "1":
                QTimer.singleShot(650, lambda: self.set_state(AngelaState.READY))
        self.page().runJavaScript(
            "document.querySelectorAll('canvas').length",
            lambda count: print("CANVAS_COUNT", count, flush=True),
        )

    def show_mini_overlay(self):
        self.mini_overlay.show()
        self.mini_overlay.raise_()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_mini_overlay()

    def set_state(self, state):
        selected = self.state_machine.transition(state)
        self.mini_overlay.set_state(selected)
        self.tray_icon.setToolTip(
            "Ângela AI · " + {
                "ready": "Pronta", "starting": "Iniciando",
                "listening": "Ouvindo", "processing": "Pensando",
                "speaking": "Falando"
            }.get(selected.value, selected.value)
        )
        self.page().runJavaScript("window.angelaSetState(" + repr(selected.value) + ")")
        statuses = {
            "ready": "Microfone ligado · diga Ângela",
            "starting": "Iniciando reconhecimento de voz",
            "listening": "Ouvindo...",
            "processing": "Processando comando...",
            "speaking": "Respondendo...",
        }
        self.chat_panel.status.setText(statuses.get(selected.value, selected.value))
        print("ANGELA_STATE", selected.value, flush=True)

    def set_voice_level(self, level):
        self.mini_overlay.set_voice_level(level)
        self.page().runJavaScript(
            f"window.angelaSetVoiceLevel({max(0.0, min(1.0, float(level))):.3f})"
        )

    def set_mic_level(self, level):
        level = max(0.0, min(1.0, float(level)))
        self.mini_overlay.set_mic_level(level)
        self.page().runJavaScript(f"window.angelaSetMicLevel({level:.3f})")
        self.chat_panel.set_microphone_level(level)

    def set_microphone_status(self, message):
        self.chat_panel.status.setText(str(message))
        print("ANGELA_MIC_STATUS", str(message), flush=True)

    def set_camera_status(self, message):
        self.chat_panel.status.setText(str(message))
        print("ANGELA_CAMERA_STATUS", str(message), flush=True)

    def show_panel(self, payload):
        self.page().runJavaScript(
            "window.angelaShowPanel(" + json.dumps(payload, ensure_ascii=False) + ")"
        )
        print("ANGELA_PANEL", len(payload.get("items", [])), flush=True)

    def show_result_view(self, payload):
        """Executado somente na thread grafica atraves do poll do coordenador."""
        from .result_window import ResultWindow
        if len(self.result_windows) >= 3:
            oldest_key = next(iter(self.result_windows))
            older = self.result_windows.pop(oldest_key)
            older.close()
        try:
            window = ResultWindow(payload)
        except (ValueError, RuntimeError, OSError) as exc:
            print("ANGELA_RESULT_WINDOW_ERROR", type(exc).__name__, flush=True)
            self.chat_panel.status.setText("Não consegui abrir a janela de resultados")
            return
        self._next_result_id += 1
        key = self._next_result_id
        self.result_windows[key] = window
        window.destroyed.connect(
            lambda _=None, key=key: self.result_windows.pop(key, None)
        )
        window.show()
        window.raise_()
        window.activateWindow()
        print("ANGELA_RESULT_WINDOW_SHOWN", str(payload.get("kind", ""))[:20], flush=True)

    def show_transcript(self, text):
        response = normalize(text).strip(' .,!?')
        confirmations = {'sim', 'confirmar', 'confirmo', 'pode', 'pode fechar', 'fechar'}
        if response in confirmations and self.pending_confirmation_command:
            # O feedback avalia 'feche a calculadora', nunca apenas 'sim'.
            self.feedback_candidate = (self.pending_confirmation_command, '')
        else:
            self.feedback_candidate = (text, '')
            self.pending_confirmation_command = None
        self.chat_panel.set_feedback_visible(False)
        self.chat_panel.set_interpretation(None)
        self.chat_panel.add_message("user", text)
        try:
            record_conversation("user", text)
        except OSError:
            print("ANGELA_HISTORY_WRITE_ERROR", flush=True)

    def show_understanding(self, text):
        self.chat_panel.set_interpretation(text)
        print("ANGELA_INTERPRETED", repr(text[:150]), flush=True)

    def show_reply(self, text):
        command = self.feedback_candidate[0]
        self.feedback_candidate = (command, text)
        spoken_reply = normalize(text)
        if 'confirmar fechamento' in spoken_reply:
            self.pending_confirmation_command = command
        elif 'solicitei ao windows que feche' in spoken_reply or 'operacao cancelada' in spoken_reply:
            self.pending_confirmation_command = None
        self.chat_panel.add_message("assistant", text)
        try:
            record_conversation("assistant", text)
        except OSError:
            print("ANGELA_HISTORY_WRITE_ERROR", flush=True)

    def show_feedback_prompt(self, show):
        self.chat_panel.set_feedback_visible(
            bool(show) and bool(self.feedback_candidate[0])
            and bool(self.feedback_candidate[1])
        )

    def show_feedback_transcript(self, text):
        # Não sobrescrever o comando que está sendo avaliado.
        self.chat_panel.add_message("user", text)
        try:
            record_conversation("user", text)
        except OSError:
            print("ANGELA_HISTORY_WRITE_ERROR", flush=True)

    def record_feedback(self, accepted):
        command, answer = self.feedback_candidate
        if not command or not answer:
            return
        try:
            save_feedback(command, answer, bool(accepted))
            print("ANGELA_FEEDBACK_SAVED", bool(accepted), flush=True)
            self.chat_panel.feedback_recorded(bool(accepted))
            self.feedback_candidate = ("", "")
        except OSError as exc:
            self.chat_panel.status.setText("Falha ao registrar feedback")
            print("ANGELA_FEEDBACK_WRITE_ERROR", type(exc).__name__, flush=True)

    def on_button_feedback(self, accepted):
        if self.voice_coordinator is not None:
            self.voice_coordinator.accept_feedback(bool(accepted))

    def export_feedback_report(self):
        try:
            target = export_report()
            self.chat_panel.report_saved(str(target))
            print("ANGELA_REPORT_SAVED", target.name, flush=True)
        except OSError as exc:
            self.chat_panel.status.setText("Falha ao salvar relatório")
            print("ANGELA_REPORT_ERROR", type(exc).__name__, flush=True)

    def _poll_voice(self):
        if self.voice_coordinator is not None:
            self.voice_coordinator.poll()

    def protect_vision_capture(self):
        # O holograma e o painel não devem contaminar a captura da janela ativa.
        from .screen_vision import protect_own_window
        results = (
            protect_own_window(int(self.winId())),
            protect_own_window(int(self.chat_panel.winId())),
            protect_own_window(int(self.mini_overlay.winId())),
        )
        print("ANGELA_VISION_OVERLAY_EXCLUDED", results, flush=True)

    def enable_voice(self):
        record('voice_enable_attempt')
        if self.voice_coordinator is None:
            self.voice_coordinator = VoiceCoordinator(self.set_state)
            self.voice_coordinator.camera_bridge = self.camera_bridge
            self.voice_coordinator.on_voice_level = self.set_voice_level
            self.voice_coordinator.on_mic_level = self.set_mic_level
            self.voice_coordinator.on_microphone_status = self.set_microphone_status
            self.voice_coordinator.on_camera_status = self.set_camera_status
            self.voice_coordinator.on_panel = self.show_panel
            self.voice_coordinator.on_result_view = self.show_result_view
            self.voice_coordinator.on_transcript = self.show_transcript
            self.voice_coordinator.on_understanding = self.show_understanding
            self.voice_coordinator.on_reply = self.show_reply
            self.voice_coordinator.on_feedback = self.record_feedback
            self.voice_coordinator.on_feedback_prompt = self.show_feedback_prompt
            self.voice_coordinator.on_feedback_text = self.show_feedback_transcript
        self.voice_timer.start(70)
        self.voice_coordinator.start()
        record('voice_enable_completed')

    def closeEvent(self, event):
        # Fecha a webcam antes do Qt, mesmo em encerramento da Ângela.
        self.camera_bridge.close_from_gui()
        self.mini_overlay.close()
        self.tray_icon.hide()
        for window in list(self.result_windows.values()):
            window.close()
        self.result_windows.clear()
        self.voice_timer.stop()
        if self.voice_coordinator is not None:
            self.voice_coordinator.stop()
        self.chat_panel.close()
        super().closeEvent(event)
        QApplication.instance().quit()


def main():
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--enable-webgl")
    app = QApplication(sys.argv)
    record('desktop_overlay_started', voice_requested=os.environ.get('ANGELA_ENABLE_VOICE') == '1')
    # O HUD e o painel usam Qt.Tool e nao contam como janelas principais.
    # Fechar a ultima janela comum (previsao, video ou resposta) nao pode
    # desligar a escuta continua nem encerrar a assistente.
    # O desligamento explicito continua em HologramOverlay.closeEvent().
    app.setQuitOnLastWindowClosed(False)
    overlay = HologramOverlay()
    overlay.show()
    overlay.chat_panel.show()
    overlay.show_mini_overlay()
    QTimer.singleShot(750, overlay.protect_vision_capture)
    if os.environ.get("ANGELA_ENABLE_VOICE", "") == "1":
        QTimer.singleShot(900, overlay.enable_voice)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
