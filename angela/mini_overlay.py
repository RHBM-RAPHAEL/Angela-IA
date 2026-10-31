"""Small draggable, always-on-top local status avatar for Angela AI.

A visual status indicator only: no independent microphone, network, AI, or
camera use. Reuses the precise state machine colors of the main HUD.
"""
from __future__ import annotations

from math import sin, pi
from pathlib import Path

from PySide6.QtCore import Qt, QPoint, QRect, QSettings, QTimer
from PySide6.QtGui import (
    QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import QApplication, QWidget, QMenu, QSystemTrayIcon

from .states import AngelaState, STATE_COLORS


STATE_LABELS = {
    AngelaState.STARTING: "INICIANDO",
    AngelaState.READY: "PRONTA",
    AngelaState.LISTENING: "OUVINDO",
    AngelaState.PROCESSING: "PENSANDO",
    AngelaState.SPEAKING: "FALANDO",
}

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
LOGO_SOURCES = (
    Path(r"D:\RHBM TechWorks\Meus Softwares\Angela-IA\assets\icone angela.png"),
    PACKAGE_ROOT / "launcher" / "assets" / "AngelaAI.ico",
)


class MiniAngelaOverlay(QWidget):
    """Small movable Qt Tool window, always visible over normal applications.

    The window receives pointer input only within its 124x146 pixel bounding
    box; the full-screen hologram remains completely click-through.
    """
    def __init__(self, parent=None, *, settings=None):
        super().__init__(parent)
        self.setObjectName("MiniAngelaOverlay")
        self.setWindowTitle("Ângela AI · Estado")
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFixedSize(124, 146)
        self.setMouseTracking(True)

        self._settings = settings if settings is not None else QSettings(
            "RHBM TechWorks", "Angela AI"
        )
        self._state = AngelaState.STARTING
        self._voice_level = 0.0
        self._mic_level = 0.0
        self._phase = 0.0
        self._drag_offset = None

        self._logo = QPixmap()
        for path in LOGO_SOURCES:
            if path.exists():
                candidate = QPixmap(str(path))
                if not candidate.isNull():
                    self._logo = candidate
                    self.setWindowIcon(QIcon(str(path)))
                    break

        self._timer = QTimer(self)
        self._timer.setInterval(90)
        self._timer.timeout.connect(self._animate)
        self._timer.start()

        self.restore_position()
        self.setToolTip(
            "Ângela AI · arraste para mover · clique direito para opções"
        )

    @property
    def state(self) -> AngelaState:
        return self._state

    def set_state(self, state: AngelaState | str):
        self._state = AngelaState(state)
        self.setToolTip(
            "Ângela AI · " + STATE_LABELS[self._state].title()
            + " · arraste para mover"
        )
        self.update()

    def set_mic_level(self, level: float):
        self._mic_level = min(1.0, max(0.0, float(level)))
        if self._state == AngelaState.LISTENING:
            self.update()

    def set_voice_level(self, level: float):
        self._voice_level = min(1.0, max(0.0, float(level)))
        if self._state in (AngelaState.SPEAKING, AngelaState.PROCESSING):
            self.update()

    def _animate(self):
        if self._state in (AngelaState.LISTENING, AngelaState.SPEAKING,
                           AngelaState.PROCESSING, AngelaState.STARTING):
            self._phase = (self._phase + 0.09) % (2 * pi)
            self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        # Compact card is the only input-catching surface, never the desktop.
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(6, 16, 30, 225))
        painter.drawRoundedRect(3, 3, 118, 139, 19, 19)

        state_color = QColor(STATE_COLORS[self._state])
        level = (self._mic_level if self._state == AngelaState.LISTENING
                 else self._voice_level if self._state == AngelaState.SPEAKING
                 else 0.0)
        motion = (0.5 + 0.5 * sin(self._phase)) if self._state in (
            AngelaState.STARTING, AngelaState.PROCESSING,
            AngelaState.LISTENING, AngelaState.SPEAKING,
        ) else 0.15

        # Backlit ring, pulsing in sync with actual listening/speaking levels.
        gradient = QRadialGradient(62, 60, 55)
        light = QColor(state_color)
        light.setAlpha(int(45 + 48 * motion + 55 * level))
        gradient.setColorAt(0.0, QColor(0, 0, 0, 0))
        gradient.setColorAt(0.76, QColor(0, 0, 0, 0))
        gradient.setColorAt(1.0, light)
        painter.setBrush(gradient)
        painter.drawEllipse(9, 7, 106, 106)

        ring = QPen(state_color)
        ring.setWidthF(3.0 + 2.0 * level + 0.7 * motion)
        painter.setPen(ring)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(17, 16, 90, 90)

        # Logo stays crisp and centered, clipped to an avatar circle.
        icon_box = QRect(25, 24, 74, 74)
        circle = QPainterPath()
        circle.addEllipse(icon_box)
        painter.setClipPath(circle)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(10, 24, 39))
        painter.drawEllipse(icon_box)
        if not self._logo.isNull():
            target = self._logo.scaled(
                icon_box.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            x = icon_box.center().x() - target.width() // 2
            y = icon_box.center().y() - target.height() // 2
            painter.drawPixmap(x, y, target)
        painter.setClipping(False)

        # Status color dot and short plain-language state below the logo.
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(state_color)
        painter.drawEllipse(22, 117, 9, 9)
        painter.setPen(QColor(230, 239, 248))
        font = QFont("Segoe UI", 9)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(
            QRect(36, 109, 73, 27),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            STATE_LABELS[self._state],
        )
        painter.end()

    def restore_position(self):
        saved = self._settings.value("mini_avatar_position")
        if isinstance(saved, QPoint):
            requested = QRect(saved, self.size())
            for screen in QApplication.screens():
                visible = screen.availableGeometry().intersected(requested)
                if visible.width() >= 40 and visible.height() >= 40:
                    self.move(saved)
                    return
        screen = QApplication.primaryScreen()
        if screen is not None:
            bounds = screen.availableGeometry()
            self.move(
                bounds.right() - self.width() - 20,
                bounds.top() + max(90, round(bounds.height() * 0.24))
            )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (self._drag_offset is not None
            and event.buttons() & Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._drag_offset is not None:
            self._drag_offset = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self._settings.setValue("mini_avatar_position", self.pos())
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        action = menu.addAction("Ocultar mini-Ângela")
        selected = menu.exec(event.globalPos())
        if selected == action and QSystemTrayIcon.isSystemTrayAvailable():
            # Windows tray offers a persistent way to show it again.
            self.hide()
        event.accept()
