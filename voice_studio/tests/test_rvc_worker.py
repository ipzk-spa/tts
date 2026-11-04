"""Тест захисту від бага tts-with-rvc: tuple замість audio array."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from voice_studio.engines.rvc_worker import _as_audio_array


def test_as_audio_array_accepts_float():
    arr = np.zeros(100, dtype=np.float32)
    out = _as_audio_array(arr)
    assert out.dtype.kind == "f"
    assert out.shape == (100,)


def test_as_audio_array_rejects_none_tuple():
    with pytest.raises(RuntimeError, match="порожній|не зміг|RVC"):
        _as_audio_array((None, None))


def test_as_audio_array_unwraps_tuple_with_array():
    inner = np.ones(50, dtype=np.float32)
    out = _as_audio_array((inner, "extra"))
    assert out.shape == (50,)
