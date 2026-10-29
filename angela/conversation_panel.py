"""Painel leve de conversas e avaliações; janela própria para receber cliques.

A esfera WebGL continua transparente ao mouse. O painel fica no fundo da
área de trabalho principal e recebe cliques somente quando está visível.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QScrollArea, QSizePolicy, QApplication,
)


class ConversationPanel(QWidget):
    feedback_selected = Signal(bool)
    export_requested = Signal()
    stop_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("conversation-panel")
        self.setWindowTitle("Ângela · Conversas")
        # Nunca ficar por cima das janelas abertas. O painel permanece
        # junto à área de trabalho, assim como o holograma passivo.
        self.setWindowFlags(
            Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
            | Qt.WindowType.WindowStaysOnBottomHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(355, 430)
        bounds = QApplication.primaryScreen().availableGeometry()
        self.move(bounds.left() + 20, bounds.top() + 18)
        self.setProperty('angela_primary_desktop_panel', True)
        self.setStyleSheet("""
          #conversation-panel { background: rgba(7, 19, 37, 236);
              border: 1px solid #367bad; border-radius: 14px; }
          QLabel { color: #dcecff; font: 12px 'Segoe UI'; }
          QLabel#panel-title { color: #86d9ff; font-size: 15px; font-weight: 700; }
          QLabel#panel-status { color: #89b2cc; font-size: 10px; }
          QLabel#interpreted { color: #b1ddeb; font-size: 10px; }
          QScrollArea, QWidget#message-container {
              background: transparent; border: none; }
          QFrame#user-message { background: #123453; border-radius: 9px; }
          QFrame#assistant-message { background: #18283b; border-radius: 9px; }
          QLabel#speaker { color: #79d4ff; font-weight: 600; font-size: 11px; }
          QFrame#feedback-box { background: #173347; border-radius: 9px; }
          QPushButton { color: #f0f8ff; background: #17476d;
              border: 1px solid #417da6; border-radius: 7px;
              padding: 5px 9px; font: 11px 'Segoe UI'; }
          QPushButton:hover { background: #246794; }
          QPushButton#yes-button { background: #17604a; border-color: #2d9874; }
          QPushButton#no-button { background: #66333d; border-color: #a65a66; }
        """)
        body = QVBoxLayout(self)
        body.setContentsMargins(12, 12, 12, 12)
        body.setSpacing(8)
        header = QHBoxLayout()
        title = QLabel("ÂNGELA · CONVERSA")
        title.setObjectName("panel-title")
        header.addWidget(title, 1)
        export_button = QPushButton("Relatório")
        export_button.setToolTip("Salvar histórico e feedback em arquivo local")
        export_button.clicked.connect(self.export_requested.emit)
        header.addWidget(export_button)
        stop_button = QPushButton('×')
        stop_button.setFixedWidth(28)
        stop_button.setToolTip('Encerrar a Ângela sem desligar o Windows')
        stop_button.clicked.connect(self.stop_requested.emit)
        header.addWidget(stop_button)
        body.addLayout(header)
        self.status = QLabel("Aguardando comando de voz")
        self.status.setObjectName("panel-status")
        body.addWidget(self.status)
        self.interpreted = QLabel("")
        self.interpreted.setObjectName("interpreted")
        self.interpreted.setTextFormat(Qt.TextFormat.PlainText)
        self.interpreted.setWordWrap(True)
        self.interpreted.hide()
        body.addWidget(self.interpreted)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.message_container = QWidget()
        self.message_container.setObjectName("message-container")
        self.message_layout = QVBoxLayout(self.message_container)
        self.message_layout.setContentsMargins(0, 0, 3, 0)
        self.message_layout.setSpacing(7)
        self.message_layout.addStretch()
        self.scroll.setWidget(self.message_container)
        body.addWidget(self.scroll, 1)
        self.entries = []
        self.feedback_box = QFrame()
        self.feedback_box.setObjectName("feedback-box")
        feedback_layout = QVBoxLayout(self.feedback_box)
        feedback_layout.setContentsMargins(9, 8, 9, 8)
        feedback_layout.setSpacing(5)
        question = QLabel("Era isso que você esperava?")
        question.setWordWrap(True)
        feedback_layout.addWidget(question)
        buttons = QHBoxLayout()
        yes = QPushButton("Sim")
        yes.setObjectName("yes-button")
        yes.clicked.connect(lambda: self.feedback_selected.emit(True))
        no = QPushButton("Não")
        no.setObjectName("no-button")
        no.clicked.connect(lambda: self.feedback_selected.emit(False))
        buttons.addWidget(yes)
        buttons.addWidget(no)
        feedback_layout.addLayout(buttons)
        feedback_layout.addWidget(QLabel('Ou diga: "sim, era" / "não, não era".'))
        self.feedback_box.hide()
        body.addWidget(self.feedback_box)
        self._last_role = None

    def add_message(self, role: str, text: str):
        frame = QFrame()
        frame.setObjectName("user-message" if role == "user" else "assistant-message")
        block = QVBoxLayout(frame)
        block.setContentsMargins(9, 7, 9, 7)
        block.setSpacing(3)
        caption = QLabel("VOCÊ · RECONHECIDO" if role == "user" else "ÂNGELA · RESPOSTA")
        caption.setObjectName("speaker")
        block.addWidget(caption)
        body = QLabel(str(text)[:1200])
        body.setTextFormat(Qt.TextFormat.PlainText)
        body.setWordWrap(True)
        body.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        block.addWidget(body)
        self.message_layout.insertWidget(self.message_layout.count() - 1, frame)
        self.entries.append(frame)
        if len(self.entries) > 24:
            oldest = self.entries.pop(0)
            self.message_layout.removeWidget(oldest)
            oldest.deleteLater()
        QTimer.singleShot(0, lambda: self.scroll.verticalScrollBar().setValue(
            self.scroll.verticalScrollBar().maximum()))

    def set_interpretation(self, text: str | None):
        summary = ("Interpretado como: " + str(text)[:125]) if text else ""
        self.interpreted.setText(summary)
        self.interpreted.setVisible(bool(summary))

    def set_feedback_visible(self, visible: bool):
        self.feedback_box.setVisible(bool(visible))

    def feedback_recorded(self, accepted: bool):
        self.feedback_box.hide()
        self.status.setText("Feedback salvo: " + ("Sim" if accepted else "Não"))

    def report_saved(self, path: str):
        self.status.setText("Relatório salvo: " + str(path).split("\\")[-1][:42])
        self.status.setToolTip(str(path))
