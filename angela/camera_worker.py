"""Processo isolado para capturar uma unica foto da webcam no Windows.

O Qt Multimedia vive somente no processo filho (thread principal Qt).
A imagem JPEG sai exclusivamente por stdout em memoria, nunca em disco.
"""
from __future__ import annotations

import sys


def main() -> int:
    from PySide6.QtGui import QGuiApplication
    from .camera_vision import _qt_capture_frame
    from .screen_vision import VisionError

    app = QGuiApplication([])
    try:
        jpeg = _qt_capture_frame(timeout_ms=6000)
        sys.stdout.buffer.write(jpeg)
        sys.stdout.buffer.flush()
        return 0
    except VisionError:
        # Nao ecoar nomes de cameras ou dados pessoais no terminal.
        return 2
    except Exception:
        return 3
    finally:
        app.quit()


if __name__ == "__main__":
    raise SystemExit(main())
