"""Tiny synthesized sound effects, written as WAV files at startup and played with winsound."""

from __future__ import annotations

import math
import os
import struct
import tempfile
import wave

RATE = 22050

# name: list of (frequency Hz, seconds); a frequency of 0 is silence.
TUNES = {
    "star": [(880, 0.05), (1320, 0.07)],
    "power": [(660, 0.06), (880, 0.06), (1100, 0.09)],
    "shieldhit": [(520, 0.05), (780, 0.07)],
    "hit": [(180, 0.09), (120, 0.14)],
    "miss": [(300, 0.06)],
    "level": [(523, 0.08), (659, 0.08), (784, 0.08), (1046, 0.14)],
    "gameover": [(392, 0.16), (330, 0.16), (262, 0.16), (196, 0.3)],
    "start": [(440, 0.06), (660, 0.08)],
    "laser": [(1500, 0.02), (1100, 0.025)],
    "boom": [(140, 0.05), (90, 0.08), (60, 0.1)],
    "split": [(200, 0.04), (320, 0.04), (110, 0.1)],
    "overheat": [(240, 0.08), (0, 0.03), (240, 0.08)],
}


def _write(path: str, notes: list[tuple[int, float]]) -> None:
    frames = bytearray()
    for freq, secs in notes:
        n = int(RATE * secs)
        for i in range(n):
            env = min(1.0, i / 200) * min(1.0, (n - i) / 400)  # soft attack and release
            v = 0.0 if freq == 0 else math.sin(math.tau * freq * i / RATE)
            # A little square-wave edge gives it an arcade feel.
            v = 0.7 * v + 0.3 * (1.0 if v > 0 else -1.0)
            frames += struct.pack("<h", int(v * env * 9000))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(frames))


class Sounds:
    def __init__(self) -> None:
        self.muted = False
        self.paths: dict[str, str] = {}
        try:
            import winsound  # Windows only

            self._winsound = winsound
            folder = os.path.join(tempfile.gettempdir(), "star_sweep_sounds")
            os.makedirs(folder, exist_ok=True)
            for name, notes in TUNES.items():
                path = os.path.join(folder, f"{name}.wav")
                if not os.path.exists(path):
                    _write(path, notes)
                self.paths[name] = path
        except Exception:
            self._winsound = None

    def play(self, name: str) -> None:
        if self.muted or self._winsound is None or name not in self.paths:
            return
        ws = self._winsound
        try:
            ws.PlaySound(self.paths[name], ws.SND_FILENAME | ws.SND_ASYNC | ws.SND_NODEFAULT)
        except Exception:
            pass
