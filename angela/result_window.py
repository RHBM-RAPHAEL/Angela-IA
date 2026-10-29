"""Janela leve e reutilizavel para resultados solicitados por voz.

Objetos Qt sao construidos apenas na thread da interface principal.
O texto vindo de IA/Internet e sempre renderizado como texto, nunca HTML.
"""
from __future__ import annotations

from urllib.parse import urlparse

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QSizePolicy,
)

_ALLOWED_VIDEO = {
    "www.youtube.com", "youtube.com", "m.youtube.com",
    "www.youtube-nocookie.com", "youtube-nocookie.com",
}


def safe_video_url(url: str) -> bool:
    if not isinstance(url, str) or len(url) > 1200:
        return False
    try:
        parsed = urlparse(url)
        return (
            parsed.scheme == "https"
            and parsed.hostname in _ALLOWED_VIDEO
            and parsed.username is None
            and parsed.password is None
            and (parsed.port is None or parsed.port == 443)
            and not any(c.isspace() for c in url)
        )
    except ValueError:
        return False


class ResultWindow(QWidget):
    def __init__(self, payload: dict, parent=None):
        super().__init__(parent=None)
        if not isinstance(payload, dict) or payload.get("kind") not in {"text", "weather", "video"}:
            raise ValueError("Tipo de resultado nao suportado")
        self.payload = payload
        self.video_view = None
        self.setObjectName("angela-result-window")
        self.setWindowTitle("Ângela · " + str(payload.get("title", "Resultado"))[:80])
        self.setWindowFlags(Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.resize(720, 490 if payload["kind"] == "video" else 430)
        self.setMinimumSize(460, 290)
        self.setStyleSheet("""
            QWidget#angela-result-window {
                background-color: #081626;
                border: 1px solid #28608e;
            }
            QLabel#result-title {
                color: #91dfff; font-size: 19px; font-weight: bold;
            }
            QLabel#result-subtitle {
                color: #c0d3e4; font-size: 12px;
            }
            QLabel#result-source {
                color: #9db4ca; font-size: 11px;
            }
            QPlainTextEdit {
                color: #eaf5ff; background-color: #10263b;
                border: 1px solid #2d5879; border-radius: 9px;
                font: 13px "Segoe UI"; padding: 12px;
            }
            QPushButton {
                color: #ecfaff; background-color: #174f7b;
                border: 1px solid #387da8; border-radius: 7px;
                padding: 8px 14px;
            }
        """)
        base = QVBoxLayout(self)
        base.setContentsMargins(22, 18, 22, 18)
        base.setSpacing(12)
        header = QHBoxLayout()
        self.title_label = QLabel(str(payload.get("title", "Resultado"))[:100])
        self.title_label.setObjectName("result-title")
        self.title_label.setWordWrap(True)
        header.addWidget(self.title_label, 1)
        close_button = QPushButton("Fechar")
        close_button.setAccessibleName("Fechar janela de resultado")
        close_button.clicked.connect(self.close)
        header.addWidget(close_button)
        base.addLayout(header)

        subtitle = str(payload.get("subtitle", ""))[:450]
        if subtitle:
            summary = QLabel(subtitle)
            summary.setObjectName("result-subtitle")
            summary.setWordWrap(True)
            summary.setTextFormat(Qt.TextFormat.PlainText)
            base.addWidget(summary)
        kind = payload["kind"]
        if kind == "video":
            url = str(payload.get("url") or "")
            if not safe_video_url(url):
                raise ValueError("Destino de video nao permitido")
            # WebEngine so e inicializado para pedidos de videos.
            from PySide6.QtWebEngineCore import QWebEnginePage
            from PySide6.QtWebEngineWidgets import QWebEngineView

            class VideoPage(QWebEnginePage):
                def acceptNavigationRequest(self, target, navigation_type, is_main_frame):
                    if is_main_frame:
                        value = target.toString()
                        if value not in {"about:blank"} and not safe_video_url(value):
                            return False
                    return super().acceptNavigationRequest(target, navigation_type, is_main_frame)

            self.video_view = QWebEngineView(self)
            self.video_view.setPage(VideoPage(self.video_view))
            self.video_view.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            base.addWidget(self.video_view, 1)
            base.addWidget(QLabel("Se o YouTube restringir a reprodução incorporada, use Abrir no navegador."))
            open_button = QPushButton("Abrir no navegador")
            open_button.setAccessibleName("Abrir vídeo ou pesquisa no navegador")
            open_button.clicked.connect(
                lambda: QDesktopServices.openUrl(QUrl(url))
            )
            base.addWidget(open_button)
            self.video_view.setUrl(QUrl(url))
        else:
            editor = QPlainTextEdit(self)
            editor.setObjectName("result-text")
            editor.setPlainText(str(payload.get("text", ""))[:7000])
            editor.setReadOnly(True)
            editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
            base.addWidget(editor, 1)
        source = str(payload.get("source") or "")
        if source:
            footer = QLabel(source[:160])
            footer.setObjectName("result-source")
            base.addWidget(footer)
        self.setGeometry(self._suggest_geometry())

    def _suggest_geometry(self):
        from PySide6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().availableGeometry()
        width = min(self.width(), screen.width())
        height = min(self.height(), screen.height())
        left = screen.left() + max(0, (screen.width() - width) // 2)
        top = screen.top() + max(0, (screen.height() - height) // 2)
        from PySide6.QtCore import QRect
        return QRect(left, top, width, height)

    def closeEvent(self, event):
        if self.video_view is not None:
            # Descarrega o player ao fechar, liberando recursos de audio/video.
            self.video_view.setUrl(QUrl("about:blank"))
        super().closeEvent(event)
