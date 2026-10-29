"""Audio amplitude envelope used solely for hologram animation."""
from __future__ import annotations

from pathlib import Path
import subprocess
import array
import math


def mp3_envelope(path: str | Path, fps: int = 20) -> list[float]:
    """Return RMS loudness per animation interval, or silence if unavailable.

    ffmpeg decoding runs without a shell. Audio playback must work even if
    this optional visualization cannot be calculated.
    """
    try:
        import imageio_ffmpeg
        executable = imageio_ffmpeg.get_ffmpeg_exe()
        result = subprocess.run(
            [executable, "-v", "error", "-i", str(path),
             "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=12, check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        samples = array.array("h")
        samples.frombytes(result.stdout[: len(result.stdout) // 2 * 2])
        window = max(1, 16000 // fps)
        levels = [
            math.sqrt(sum(value * value for value in samples[i:i + window]) /
                      max(1, len(samples[i:i + window]))) / 32768
            for i in range(0, len(samples), window)
        ]
        if not levels:
            return [0.0]
        ceiling = max(0.025, sorted(levels)[int(.92 * (len(levels) - 1))])
        return [min(1.0, (value / ceiling) ** .75) for value in levels]
    except Exception:
        return [0.0]
