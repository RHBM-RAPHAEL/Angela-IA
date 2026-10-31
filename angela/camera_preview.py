"""Opt-in local live webcam preview and cross-thread, one-frame snapshots.

Only Qt GUI thread owns QCamera and its QVideoSink. Worker threads communicate
with queued Qt signals and wait on private Events. No continuous image upload,
audio/video recording, remote network calls, or frames written to disk.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from threading import Event
import os

from PySide6.QtCore import QObject, Qt, Signal, QTimer, QBuffer, QByteArray, QIODevice, QThread
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QApplication
from PySide6.QtMultimedia import QCamera, QMediaCaptureSession, QMediaDevices
from PySide6.QtMultimediaWidgets import QVideoWidget

from .audit_log import record


@dataclass
class _CameraTask:
    action: str
    done: Event = field(default_factory=Event)
    value: object = None
    error: str = ""

    def complete(self, *, value=None, error=""):
        if self.done.is_set():
            return
        self.value = value
        self.error = error
        self.done.set()


class CameraPreviewWindow(QWidget):
    closed = Signal()
    failed = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ângela AI · Visão computacional")
        self.setWindowFlags(
            Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
        self.resize(420, 315)
        self.setMinimumSize(310, 220)
        self.setStyleSheet(
            "QWidget { background: #131c29; color: #e7f3ff; }"
            "QPushButton { border: 1px solid #3b668a; border-radius: 7px;"
            " background: #1c3550; padding: 6px 13px; }"
            "QLabel { font-size: 12px; }"
        )

        layout = QVBoxLayout(self)
        title_row = QHBoxLayout()
        title_row.addWidget(QLabel("VISÃO COMPUTACIONAL · AO VIVO"))
        title_row.addStretch()
        stop_button = QPushButton("Fechar câmera")
        stop_button.setAccessibleName("Fechar câmera")
        stop_button.clicked.connect(self.close)
        title_row.addWidget(stop_button)
        layout.addLayout(title_row)

        self.video = QVideoWidget(self)
        self.video.setMinimumHeight(155)
        layout.addWidget(self.video, 1)
        layout.addWidget(QLabel(
            "Prévia local · nada é enviado automaticamente à IA"
        ))

        devices = list(QMediaDevices.videoInputs())
        if not devices:
            raise RuntimeError("Nenhuma webcam disponível no Windows.")
        try:
            index = int(os.environ.get("ANGELA_CAMERA_INDEX", "0"))
        except ValueError:
            raise RuntimeError("Índice de webcam inválido.") from None
        if index < 0 or index >= len(devices):
            raise RuntimeError("A webcam configurada não foi encontrada.")
        self.camera = QCamera(devices[index], self)
        self.session = QMediaCaptureSession(self)
        self.session.setCamera(self.camera)
        self.session.setVideoOutput(self.video)
        self.camera.errorOccurred.connect(self._camera_error)

        screen = QApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            self.move(
                area.right() - self.width() - 24,
                area.top() + 70,
            )

    def start(self):
        self.show()
        self.raise_()
        self.camera.start()

    def _camera_error(self, _code, _description):
        record("live_camera_error", category="qcamera")
        self.failed.emit("A câmera não conseguiu iniciar. Verifique as permissões.")
        self.close()

    def capture_jpeg(self) -> bytes | None:
        """Read only the currently displayed frame, when specifically asked."""
        frame = self.video.videoSink().videoFrame()
        if not frame.isValid():
            return None
        image = frame.toImage()
        if image.isNull() or min(image.width(), image.height()) < 80:
            return None
        image = image.scaled(
            1280, 1280, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        payload = QByteArray()
        buffer = QBuffer(payload)
        try:
            if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
                return None
            if not image.save(buffer, "JPEG", 78):
                return None
            output = bytes(payload)
            return output if 0 < len(output) <= 3_000_000 else None
        finally:
            buffer.close()

    def closeEvent(self, event):
        self.camera.stop()
        self.session.setVideoOutput(None)
        self.session.setCamera(None)
        self.closed.emit()
        super().closeEvent(event)


class CameraPreviewBridge(QObject):
    """Thread-safe, local preview API called by the assistant engine.

    Construct on Qt GUI thread. May receive .open(), .close(), .snapshot()
    from an engine worker thread. All QCamera operations stay on GUI thread.
    """
    requested = Signal(object)

    def __init__(self, parent=None, *, window_factory=CameraPreviewWindow,
                 status_callback=None):
        super().__init__(parent)
        self.window_factory = window_factory
        self.status_callback = status_callback or (lambda message: None)
        self.window = None
        self._active = Event()
        self.requested.connect(self._dispatch, Qt.ConnectionType.QueuedConnection)

    def is_active(self) -> bool:
        return self._active.is_set()

    def _request(self, action: str, timeout: float):
        task = _CameraTask(action)
        if QThread.currentThread() == self.thread():
            # Chamadas na própria thread Qt não devem esperar por seu evento.
            self._dispatch(task)
        else:
            self.requested.emit(task)
        if not task.done.wait(timeout):
            task.complete(error="A câmera não respondeu a tempo.")
        if task.error:
            raise RuntimeError(task.error)
        return task.value

    def open(self):
        return bool(self._request("open", timeout=8))

    def close(self):
        return bool(self._request("close", timeout=5))

    def snapshot(self) -> bytes:
        return self._request("snapshot", timeout=8)

    def close_from_gui(self):
        """Only for the overlay's Qt closeEvent. Never creates a new camera."""
        if self.window is not None:
            self.window.close()
        self._active.clear()
        self.window = None

    def _on_closed(self):
        self._active.clear()
        self.window = None
        record("live_camera_closed")

    def _on_error(self, message: str):
        record("live_camera_unavailable", reason="hardware_or_permission")
        self.status_callback(message)

    def _dispatch(self, task: _CameraTask):
        if task.done.is_set():
            return
        if task.action == "open":
            if self._active.is_set():
                if self.window is not None:
                    self.window.raise_()
                task.complete(value=True)
                return
            try:
                window = self.window_factory()
                window.closed.connect(self._on_closed)
                window.failed.connect(self._on_error)
                self.window = window
                window.start()
                if not window.isVisible():
                    raise RuntimeError("A webcam não conseguiu abrir.")
                self._active.set()
                record("live_camera_opened", local_preview=True)
                task.complete(value=True)
            except (RuntimeError, OSError, ValueError) as exc:
                if self.window is not None:
                    self.window.close()
                self.window = None
                self._active.clear()
                record("live_camera_open_failed", reason=type(exc).__name__)
                task.complete(error=str(exc)[:140])
            return
        if task.action == "close":
            was_open = self._active.is_set()
            self.close_from_gui()
            task.complete(value=was_open)
            return
        if task.action == "snapshot":
            self._deliver_snapshot(task, attempt=0)

    def _deliver_snapshot(self, task: _CameraTask, attempt: int):
        if task.done.is_set():
            return
        if not self._active.is_set() or self.window is None:
            task.complete(error="A câmera ao vivo está fechada.")
            return
        try:
            data = self.window.capture_jpeg()
        except (RuntimeError, OSError, ValueError) as exc:
            task.complete(error="Não foi possível ler a câmera.")
            return
        if data:
            record("live_camera_snapshot", size_bytes=len(data))
            task.complete(value=data)
        elif attempt < 25:
            QTimer.singleShot(160, lambda: self._deliver_snapshot(task, attempt + 1))
        else:
            task.complete(error="A câmera ainda não produziu uma imagem legível.")
