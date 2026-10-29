"""Aprimoramento de captura de voz local: ganho limitado e áudio mono 16 kHz.

Não grava áudio em disco, não modifica a sensibilidade do Windows e não usa IA
na nuvem. A adaptação preserva o silêncio e limita clipping/distorsão.
Compatível com Python 3.11/3.12; usa audioop da biblioteca padrão.
"""
from __future__ import annotations

import audioop
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class CaptureConfig:
    device: int | None
    sample_rate: int
    source: str


def capture_candidates(sd) -> list[CaptureConfig]:
    """WASAPI para o mesmo microfone padrão, seguido do dispositivo padrão.

    PortAudio/Windows MME frequentemente converte a taxa e expõe nome truncado.
    Captura WASAPI em taxa nativa e converte internamente para 16 kHz.
    """
    configured = os.environ.get("ANGELA_MIC_DEVICE", "").strip().lower()
    if configured in {"default", "padrao", "padrão"}:
        prefer_native = False
        explicit = None
    elif configured:
        try:
            explicit = int(configured)
            sd.query_devices(explicit, "input")
            prefer_native = False
        except (ValueError, TypeError) as exc:
            raise ValueError("ANGELA_MIC_DEVICE deve ser índice numérico ou 'default'.") from exc
    else:
        explicit = None
        prefer_native = os.environ.get("ANGELA_MIC_PREFER_WASAPI", "1") != "0"

    default_index = int(sd.default.device[0])
    device = explicit if explicit is not None else default_index
    default_info = sd.query_devices(default_index, "input")
    selected_info = sd.query_devices(device, "input")
    if not selected_info.get("max_input_channels", 0):
        raise ValueError("Dispositivo selecionado não oferece entrada de áudio.")
    candidates: list[CaptureConfig] = []

    if prefer_native:
        base = " ".join(str(default_info["name"]).casefold().split())[:17]
        for index, info in enumerate(sd.query_devices()):
            if not info.get("max_input_channels", 0):
                continue
            try:
                api_name = str(sd.query_hostapis(info["hostapi"])["name"]).lower()
                if "wasapi" not in api_name or base not in " ".join(info["name"].casefold().split()):
                    continue
                rate = int(round(info["default_samplerate"]))
                sd.check_input_settings(device=index, channels=1, samplerate=rate, dtype="int16")
                candidates.append(CaptureConfig(index, rate, "wasapi-native"))
            except Exception:
                # Falhas do driver não devem impedir o fallback.
                continue
        # Algumas matrizes Intel Smart Sound retornam silêncio digital pelo
        # mixer do Windows, mesmo com entrada física funcionando. WDM-KS pode
        # disponibilizar o mesmo conjunto de microfones sem a supressão.
        for index, info in enumerate(sd.query_devices()):
            if not info.get("max_input_channels", 0):
                continue
            try:
                api_name = str(sd.query_hostapis(info["hostapi"])["name"]).lower()
                name = " ".join(str(info["name"]).casefold().split())
                if "wdm-ks" not in api_name or base not in name:
                    continue
                rate = int(round(info["default_samplerate"]))
                sd.check_input_settings(device=index, channels=1, samplerate=rate, dtype="int16")
                candidates.append(CaptureConfig(index, rate, "wdmks-raw"))
            except Exception:
                continue

    if explicit is not None:
        rate = int(round(selected_info["default_samplerate"]))
        candidates = [CaptureConfig(device, rate, "manual")]
    else:
        candidates.append(CaptureConfig(default_index, 16000, "default-16k"))
        native_rate = int(round(default_info["default_samplerate"]))
        if native_rate != 16000:
            candidates.append(CaptureConfig(default_index, native_rate, "default-native"))
    # Evita repetições quando o usuário altera o dispositivo padrão.
    return list(dict.fromkeys(candidates))


class AdaptiveGain:
    """AGC limitado que não amplifica o ruído constante como se fosse fala."""

    def __init__(self, *, target_rms: int = 2200, max_gain: float = 10.0):
        # O WDM-KS do notebook pode fornecer falas com PCM extremamente baixo.
        # O teto protege a saída de saturação mesmo com captura silenciosa.
        self.max_gain = max(1.0, min(float(max_gain), 12.0))
        self.target_rms = max(600, min(int(target_rms), 4000))
        self.gain = 1.0
        self.ambient_rms = 40.0
        self.last_input_rms = 0
        self.last_output_rms = 0
        self.last_peak = 0

    def process(self, raw: bytes) -> bytes:
        if len(raw) < 2 or len(raw) % 2:
            return raw
        rms = audioop.rms(raw, 2)
        peak = audioop.max(raw, 2)
        self.last_input_rms = rms
        self.last_peak = peak

        # Estimar o ruído apenas em blocos silenciosos: a versão anterior
        # aprendia falas fracas como "ruído" e depois deixava de amplificá-las.
        if rms <= max(12.0, self.ambient_rms * 1.45):
            coefficient = 0.065 if rms < self.ambient_rms else 0.01
            self.ambient_rms += coefficient * (rms - self.ambient_rms)
        threshold = max(12.0, self.ambient_rms * 1.85)
        speech = rms >= threshold
        if speech:
            desired = min(
                self.max_gain, self.target_rms / max(1.0, rms),
                29000.0 / max(1.0, peak),
            )
            desired = max(1.0, desired)
        else:
            desired = 1.0

        # Resposta gradual, com redução rápida para evitar clipping.
        factor = 0.45 if desired < self.gain else 0.25
        self.gain += (desired - self.gain) * factor
        applied = min(self.gain, 29000.0 / max(1.0, peak))
        applied = max(0.1, applied)
        amplified = audioop.mul(raw, 2, applied) if abs(applied-1.0) > 0.01 else raw
        self.last_output_rms = audioop.rms(amplified, 2)
        return amplified


class AudioFrontend:
    """Resampling streaming preserva o estado do filtro entre os blocos."""

    OUTPUT_RATE = 16000

    def __init__(self, capture_rate: int, *, max_gain: float | None = None):
        if not 8000 <= int(capture_rate) <= 192000:
            raise ValueError("Taxa de amostragem inválida.")
        if max_gain is None:
            try:
                max_gain = float(os.environ.get("ANGELA_MIC_MAX_GAIN", "10.0"))
            except ValueError:
                max_gain = 10.0
        self.rate = int(capture_rate)
        self.agc = AdaptiveGain(max_gain=max_gain)
        self._resample_state = None

    def process(self, chunk: bytes) -> bytes:
        if self.rate != self.OUTPUT_RATE:
            chunk, self._resample_state = audioop.ratecv(
                chunk, 2, 1, self.rate, self.OUTPUT_RATE, self._resample_state,
                1, 0,
            )
        return self.agc.process(chunk)

    def reset(self) -> None:
        self._resample_state = None
        # Mantém uma estimativa de ruído útil, mas reinicia ganho entre falas
        self.agc.gain = 1.0
