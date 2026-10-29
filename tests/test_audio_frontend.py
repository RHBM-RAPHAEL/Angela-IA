"""Testes do processamento do microfone (sem dispositivo real ou gravação)."""
from __future__ import annotations

import math
import os
import struct
import unittest
from unittest.mock import patch

from angela.audio_frontend import AdaptiveGain, AudioFrontend, capture_candidates
from angela.wake import choose_wake_transcript


def tone(amplitude: int, count: int = 1600, rate: int = 16000) -> bytes:
    return struct.pack(
        "<" + "h" * count,
        *(int(amplitude * math.sin(i * 2 * math.pi * 440 / rate)) for i in range(count))
    )


class FakeSoundDevice:
    class Default:
        device = [1, 3]
    default = Default()

    def __init__(self):
        self.items = [
            {"name": "Microfone USB", "hostapi": 0, "default_samplerate": 44100,
             "max_input_channels": 1},
            {"name": "Grupo de microfones (Tecnologia", "hostapi": 0,
             "default_samplerate": 44100, "max_input_channels": 4},
            {"name": "Alto-falante", "hostapi": 1, "default_samplerate": 48000,
             "max_input_channels": 0},
            {"name": "Grupo de microfones (Tecnologia Intel Smart Sound)",
             "hostapi": 1, "default_samplerate": 48000, "max_input_channels": 2},
        ]

    def query_devices(self, index=None, kind=None):
        if index is None:
            return self.items
        return self.items[index]

    def query_hostapis(self, index):
        return {"name": {0: "MME", 1: "Windows WASAPI",
                         2: "Windows WDM-KS"}.get(index, "MME")}

    def check_input_settings(self, **kwargs):
        if kwargs["samplerate"] != 48000:
            raise ValueError("Unsupported sample rate")


class AudioFrontendTests(unittest.TestCase):
    def test_ganho_para_voz_baixa(self):
        agc = AdaptiveGain(max_gain=5)
        raw = tone(360)
        baseline = __import__("audioop").rms(raw, 2)
        outputs = [agc.process(raw) for _ in range(18)]
        result = __import__("audioop").rms(outputs[-1], 2)
        self.assertGreater(result, baseline * 2.0)
        self.assertLessEqual(agc.gain, 5.0)

    def test_silencio_nao_gera_ativacao(self):
        agc = AdaptiveGain()
        empty = b"\x00\x00" * 1600
        for _ in range(30):
            self.assertEqual(agc.process(empty), empty)
        self.assertAlmostEqual(agc.gain, 1.0, places=2)
        self.assertEqual(agc.last_output_rms, 0)

    def test_voz_muito_baixa_aumenta_sem_amplificar_silencio(self):
        agc = AdaptiveGain()
        for _ in range(25):
            agc.process(b"\x00\x00" * 1600)
        raw = tone(110)
        baseline = __import__("audioop").rms(raw, 2)
        for _ in range(15):
            amplified = agc.process(raw)
        self.assertGreater(__import__("audioop").rms(amplified, 2), baseline * 2)

    def test_sinal_forte_nao_satura(self):
        agc = AdaptiveGain(max_gain=8.0)
        quiet = tone(500)
        for _ in range(15):
            agc.process(quiet)
        loud = tone(30000)
        adjusted = agc.process(loud)
        peak = __import__("audioop").max(adjusted, 2)
        self.assertLessEqual(peak, 30000)
        self.assertEqual(len(adjusted), len(loud))

    def test_volume_muito_baixo_apos_ruido_de_fundo(self):
        agc = AdaptiveGain()
        quiet_background = tone(6)
        for _ in range(45):
            agc.process(quiet_background)
        low_voice = tone(45)
        initial_rms = __import__("audioop").rms(low_voice, 2)
        for _ in range(20):
            boosted = agc.process(low_voice)
        self.assertGreater(__import__("audioop").rms(boosted, 2), initial_rms * 4)
        self.assertLessEqual(agc.gain, 12.0)

    def test_ruido_baixo_estavel_nao_amplifica_silencio(self):
        agc = AdaptiveGain()
        ambient = tone(6)
        for _ in range(60):
            boosted = agc.process(ambient)
        self.assertLessEqual(agc.gain, 1.05)
        self.assertLessEqual(__import__("audioop").rms(boosted, 2), 6)

    def test_entrada_invalida_preservada(self):
        self.assertEqual(AdaptiveGain().process(b"\x01"), b"\x01")

    def test_conversao_streaming_48k_para_16k(self):
        frontend = AudioFrontend(48000)
        raw = tone(900, count=4800, rate=48000)
        chunks = [frontend.process(raw) for _ in range(10)]
        self.assertEqual(sum(len(x) for x in chunks), 32000)
        self.assertGreater(frontend.agc.last_output_rms, 0)

    def test_16k_nao_altera_tamanho(self):
        frontend = AudioFrontend(16000)
        self.assertEqual(len(frontend.process(tone(600))), 3200)

    def test_microfone_estereo_prioriza_canal_com_voz(self):
        left = struct.unpack("<1600h", tone(110))
        right = struct.unpack("<1600h", tone(1400))
        interleaved = b"".join(struct.pack("<hh", a, b)
                               for a, b in zip(left, right))
        frontend = AudioFrontend(16000, input_channels=2)
        result = frontend.process(interleaved)
        self.assertEqual(len(result), 3200)
        self.assertEqual(frontend.selected_channel, 1)
        self.assertGreater(__import__("audioop").rms(result, 2),
                           __import__("audioop").rms(tone(110), 2) * 5)

    def test_microfones_fora_de_fase_nao_se_cancelam(self):
        left = struct.unpack("<1600h", tone(1400))
        interleaved = b"".join(struct.pack("<hh", s, -s) for s in left)
        frontend = AudioFrontend(16000, input_channels=2)
        result = frontend.process(interleaved)
        self.assertGreater(__import__("audioop").rms(result, 2), 500)

    def test_canais_invalidos_rejeitados(self):
        with self.assertRaises(ValueError):
            AudioFrontend(16000, input_channels=4)

    def test_reiniciar_ganho_entre_turnos(self):
        frontend = AudioFrontend(16000)
        for _ in range(10):
            frontend.process(tone(480))
        self.assertGreater(frontend.agc.gain, 1.0)
        frontend.reset()
        self.assertEqual(frontend.agc.gain, 1.0)

    def test_selecao_wasapi_com_fallback(self):
        with patch.dict(os.environ, {"ANGELA_MIC_PREFER_WASAPI": "1"}, clear=False):
            sd = FakeSoundDevice()
            result = capture_candidates(sd)
        self.assertEqual(result[0].source, "wasapi-native")
        self.assertEqual((result[0].device, result[0].sample_rate), (3, 48000))
        self.assertEqual(result[1].source, "default-16k")

    def test_wdmks_do_mesmo_conjunto_de_microfones_e_fallback(self):
        sd = FakeSoundDevice()
        sd.items.append({
            "name": "Grupo de microfones 2 ()", "hostapi": 2,
            "default_samplerate": 48000, "max_input_channels": 2,
        })
        with patch.dict(os.environ, {"ANGELA_MIC_PREFER_WASAPI": "1"}, clear=False):
            result = capture_candidates(sd)
        self.assertEqual(result[0].source, "wasapi-native")
        self.assertIn("wdmks-raw", [item.source for item in result])
        self.assertEqual(result[1].device, 4)
        self.assertEqual(result[1].channels, 2)
        self.assertEqual(result[-2].source, "default-16k")

    def test_escolher_dispositivo_padrao(self):
        with patch.dict(os.environ, {"ANGELA_MIC_DEVICE": "default"}):
            result = capture_candidates(FakeSoundDevice())
        self.assertEqual(result[0].device, 1)
        self.assertEqual(result[0].sample_rate, 16000)
        self.assertNotIn("wasapi-native", [candidate.source for candidate in result])

    def test_transcricao_comando_junto_a_palavra(self):
        self.assertEqual(
            choose_wake_transcript("angela abra o opera", "angela"),
            "angela abra o opera"
        )
        self.assertEqual(choose_wake_transcript("a menina falou", "angela"), "angela")
        self.assertEqual(choose_wake_transcript("anjela abra calculadora", "angela"),
                         "anjela abra calculadora")


if __name__ == "__main__":
    unittest.main()
