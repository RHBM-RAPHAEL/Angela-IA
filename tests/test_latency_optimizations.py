"""Testes controlados de streaming, trace sem conteúdo e isolamento de UI."""
from __future__ import annotations

import os
import sys
import threading
import time
import types
import unittest
from unittest.mock import Mock, patch

from angela.streaming_tts import buffered_segments, split_phrases
from angela.speech import _speak_edge_fast, speak
from angela.perf_metrics import metric, measure_ms
from angela.voice_coordinator import VoiceCoordinator


class LatencyTests(unittest.TestCase):
    def test_split_preserves_all_words(self):
        original = "Olá. Esta é uma frase bem longa de exemplo com conteúdo."
        self.assertEqual(" ".join(split_phrases(original, maximum=23)).split(),
                         original.split())

    def test_prefetch_overlaps_playback(self):
        started = threading.Event()
        released = threading.Event()
        def fake_network(_text, _voice, on_segment):
            on_segment(b"segmento-1", 0)
            started.set()
            released.wait(timeout=1.5)
            on_segment(b"segmento-2", 1)

        output = buffered_segments(
            "Uma frase. Outra frase.", "pt-BR", synthesis=fake_network
        )
        self.assertEqual(next(output), (0, b"segmento-1"))
        self.assertTrue(started.wait(timeout=0.3))
        released.set()
        self.assertEqual(next(output), (1, b"segmento-2"))
        with self.assertRaises(StopIteration):
            next(output)

    def test_synthesis_failure_stops_without_hanging(self):
        def bad(*_args):
            raise RuntimeError("API inacessível")
        with self.assertRaisesRegex(RuntimeError, "RuntimeError"):
            list(buffered_segments("Olá", "pt-BR", synthesis=bad))

    def test_first_audio_callback_and_reactive_levels(self):
        marks = []
        class Music:
            def load(self, *_args): pass
            def set_volume(self, *_args): pass
            def play(self): marks.append(time.perf_counter())
            def get_busy(self): return False
            def stop(self): pass
            def unload(self): pass
        class Mixer:
            music = Music()
            def init(self): pass
            def quit(self): pass
        pg = types.ModuleType("pygame")
        pg.mixer = Mixer()
        with (
            patch.dict(sys.modules, {"pygame": pg}),
            patch("angela.streaming_tts.buffered_segments",
                  return_value=iter([(0, b"fake1"), (1, b"fake2")])) as synth,
        ):
            onset = Mock()
            levels = Mock()
            result = _speak_edge_fast("Olá. Mundo.", on_level=levels, on_first_audio=onset)
        self.assertIn("Thalita", result)
        self.assertEqual(len(marks), 2)
        onset.assert_called_once()
        self.assertTrue(levels.called)
        synth.assert_called_once()

    def test_auto_prefers_streaming_with_reversible_flag(self):
        with patch.dict(os.environ, {"ANGELA_TTS_STREAMING": "1"}):
            with patch("angela.speech._speak_edge_fast", return_value="Thalita streaming") as stream:
                with patch("angela.speech._speak_edge") as old:
                    self.assertEqual(speak("Olá"), "Thalita streaming")
                    stream.assert_called_once()
                    old.assert_not_called()
        with patch.dict(os.environ, {"ANGELA_TTS_STREAMING": "0"}):
            with patch("angela.speech._speak_edge", return_value="Thalita antiga") as old:
                self.assertEqual(speak("Olá"), "Thalita antiga")
                old.assert_called_once()

    def test_opt_in_only_and_no_content_in_metric(self):
        with patch("angela.audit_log.record") as logger:
            with patch.dict(os.environ, {"ANGELA_PERF_DIAGNOSTICS": "0"}):
                metric("tts_first_audio", 55)
            logger.assert_not_called()
            with patch.dict(os.environ, {"ANGELA_PERF_DIAGNOSTICS": "1"}):
                metric("tts_first_audio", 35.123456)
            logger.assert_called_once()
            args = logger.call_args
            self.assertEqual(args.kwargs["phase"], "tts_first_audio")
            self.assertEqual(args.kwargs["duration_ms"], 35.123)
            self.assertNotIn("text", str(args))
            self.assertNotIn("audio", args.kwargs)
            logger.reset_mock()
            with patch.dict(os.environ, {"ANGELA_PERF_DIAGNOSTICS": "1"}):
                metric("secret_custom_event", 5)
            logger.assert_not_called()

    def test_coordinator_first_audio_tracks_command(self):
        coordinator = VoiceCoordinator(Mock())
        coordinator.listener = Mock()
        coordinator.active = True
        coordinator._command_ready_ns = time.perf_counter_ns() - 3_000_000
        callbacks = []
        def fake_thread(*args, **kwargs):
            job = Mock()
            job.start.side_effect = lambda: callbacks.append(kwargs["target"])
            return job
        with (
            patch("angela.voice_coordinator.threading.Thread", side_effect=fake_thread),
            patch("angela.speech.speak", return_value="Thalita") as voice,
            patch("angela.voice_coordinator.metric") as logger,
        ):
            coordinator._speak_async("Bom dia", False)
            callbacks[0]()
            voice.call_args.kwargs["on_first_audio"]()
        self.assertTrue(any(call.args[0] == "voice_end_to_audio" for call in logger.call_args_list))


if __name__ == "__main__":
    unittest.main()
