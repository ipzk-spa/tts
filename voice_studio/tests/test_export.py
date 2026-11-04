"""Тести експорту WAV/MP3."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from voice_studio.audio.export import save_mp3_file, save_wav_file, to_mp3_bytes, to_wav_bytes


def test_to_wav_bytes():
    audio = np.sin(np.linspace(0, 1, 1000)).astype(np.float32) * 0.5
    data = to_wav_bytes(22050, audio)
    assert data[:4] == b"RIFF"
    assert len(data) > 100


def test_save_wav_file():
    audio = np.zeros(500, dtype=np.float32)
    with tempfile.TemporaryDirectory() as td:
        path = str(Path(td) / "test.wav")
        save_wav_file(path, 22050, audio)
        assert Path(path).stat().st_size > 44


def test_to_mp3_bytes_or_none():
    audio = np.sin(np.linspace(0, 2, 2000)).astype(np.float32) * 0.3
    data = to_mp3_bytes(22050, audio)
    if data is not None:
        assert len(data) > 100
        assert data[:3] in (b"ID3", b"\xff\xfb", b"\xff\xf3")


def test_save_mp3_file_roundtrip():
    audio = np.sin(np.linspace(0, 1, 4000)).astype(np.float32) * 0.4
    with tempfile.TemporaryDirectory() as td:
        path = str(Path(td) / "test.mp3")
        result = save_mp3_file(path, 22050, audio)
        if result:
            assert Path(result).stat().st_size > 50
