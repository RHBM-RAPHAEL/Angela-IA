"""Compact always-on-top Angela HUD: only GUI simulation, no microphone."""
from __future__ import annotations

import inspect
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt, QPoint, QPointF, QSettings
from PySide6.QtWidgets import QApplication
from angela.states import AngelaState, STATE_COLORS
from angela.mini_overlay import MiniAngelaOverlay, STATE_LABELS


class _Mouse:
    def __init__(self, point, *, button=None, buttons=None):
        self._point = QPointF(point)
        self._button = button or Qt.MouseButton.LeftButton
        self._buttons = buttons if buttons is not None else Qt.MouseButton.LeftButton
        self.accepted = False
    def button(self):
        return self._button
    def buttons(self):
        return self._buttons
    def globalPosition(self):
        return self._point
    def accept(self):
        self.accepted = True


class MiniStatusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = TemporaryDirectory()
        ini = str(Path(self.folder.name) / "prefs.ini")
        self.settings = QSettings(ini, QSettings.Format.IniFormat)
        self.mini = MiniAngelaOverlay(settings=self.settings)

    def tearDown(self):
        self.mini.close()
        self.mini.deleteLater()
        self.settings.clear()
        self.folder.cleanup()

    def test_is_small_draggable_topmost_not_fullscreen(self):
        self.assertLessEqual(self.mini.width(), 130)
        self.assertLessEqual(self.mini.height(), 160)
        flags = self.mini.windowFlags()
        self.assertTrue(flags & Qt.WindowType.WindowStaysOnTopHint)
        self.assertTrue(flags & Qt.WindowType.FramelessWindowHint)
        self.assertTrue(flags & Qt.WindowType.WindowDoesNotAcceptFocus)
        self.assertTrue(self.mini.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground))
        self.assertIsNone(self.mini.parent())
        self.assertFalse(self.mini._logo.isNull(), "Use existing wolf logo")

    def test_all_five_real_states_share_hologram_colors(self):
        self.assertEqual(set(AngelaState), set(STATE_LABELS))
        for state in AngelaState:
            with self.subTest(state=state.value):
                self.mini.set_state(state)
                self.assertEqual(self.mini.state, state)
                self.assertTrue(STATE_COLORS[state].startswith("#"))
                self.assertTrue(STATE_LABELS[state])
                self.mini.set_mic_level(.76)
                self.mini.set_voice_level(.39)
                self.assertIn(STATE_LABELS[state].title(), self.mini.toolTip())
        self.mini.set_state(AngelaState.LISTENING.value)
        self.assertEqual(self.mini.state, AngelaState.LISTENING)
        self.assertAlmostEqual(self.mini._mic_level, .76)

    def test_render_on_offscreen_qt(self):
        self.mini.show()
        self.app.processEvents()
        picture = self.mini.grab()
        self.assertEqual(picture.width(), self.mini.width())
        self.assertEqual(picture.height(), self.mini.height())
        self.assertFalse(picture.isNull())

    def test_draggable_position_saved_for_next_launch(self):
        self.mini.show()
        self.app.processEvents()
        original = self.mini.pos()
        start = QPoint(original.x() + 35, original.y() + 32)
        end = QPoint(start.x() - 55, start.y() + 45)
        start_event = _Mouse(start)
        self.mini.mousePressEvent(start_event)
        self.assertTrue(start_event.accepted)
        move_event = _Mouse(end)
        self.mini.mouseMoveEvent(move_event)
        self.assertTrue(move_event.accepted)
        release_event = _Mouse(end)
        self.mini.mouseReleaseEvent(release_event)
        self.assertTrue(release_event.accepted)
        self.assertEqual(self.mini.pos(), original + QPoint(-55, 45))
        self.assertEqual(self.settings.value("mini_avatar_position"), self.mini.pos())

        other = MiniAngelaOverlay(settings=self.settings)
        self.assertEqual(other.pos(), self.mini.pos())
        other.close()
        other.deleteLater()

    def test_status_integration_with_main_hud(self):
        # Verifies the actual state callbacks are connected to this widget;
        # does not require a running WebEngine HTTP server for this test.
        from angela.desktop_overlay import HologramOverlay, main
        self.assertIn("self.mini_overlay.set_state(selected)",
                      inspect.getsource(HologramOverlay.set_state))
        self.assertIn("self.mini_overlay.set_voice_level(level)",
                      inspect.getsource(HologramOverlay.set_voice_level))
        self.assertIn("self.mini_overlay.set_mic_level(level)",
                      inspect.getsource(HologramOverlay.set_mic_level))
        self.assertIn("overlay.show_mini_overlay()", inspect.getsource(main))
        self.assertIn("self.mini_overlay.close()", inspect.getsource(
            HologramOverlay.closeEvent
        ))

    def test_not_camera_or_audio_owner(self):
        source = inspect.getsource(MiniAngelaOverlay)
        for item in ("QCamera(", "sounddevice", "GroqChat(", "WakeListener("):
            self.assertNotIn(item, source)


if __name__ == "__main__":
    unittest.main()
