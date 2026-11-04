"""DSP-допоміжні функції для аудіо (тиша, нормалізація, громкість)."""
from __future__ import annotations

import numpy as np


def make_silence(seconds: float, sr: int) -> np.ndarray:
    return np.zeros(int(max(0.0, seconds) * sr), dtype=np.float32)


def normalize_peak(audio: np.ndarray, target: float = 0.95) -> np.ndarray:
    if audio.size == 0:
        return audio
    peak = float(np.max(np.abs(audio))) or 1.0
    return (audio / peak * target).astype(np.float32)
