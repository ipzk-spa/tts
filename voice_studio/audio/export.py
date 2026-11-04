"""Експорт аудіо у WAV та MP3 без залежності від системного ffmpeg
(використовує бінарник, що постачається пакетом imageio-ffmpeg)."""
from __future__ import annotations

import io

import numpy as np
import scipy.io.wavfile as wavfile

_ffmpeg_ready = False


def _ensure_ffmpeg() -> None:
    global _ffmpeg_ready
    if _ffmpeg_ready:
        return
    try:
        import imageio_ffmpeg
        from pydub import AudioSegment

        AudioSegment.converter = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    _ffmpeg_ready = True


def float_to_int16(audio: np.ndarray) -> np.ndarray:
    audio = np.clip(audio, -1.0, 1.0)
    return (audio * 32767).astype(np.int16)


def to_wav_bytes(sample_rate: int, audio: np.ndarray) -> bytes:
    buf = io.BytesIO()
    wavfile.write(buf, sample_rate, float_to_int16(audio))
    return buf.getvalue()


def to_mp3_bytes(sample_rate: int, audio: np.ndarray, bitrate: str = "192k") -> bytes | None:
    _ensure_ffmpeg()
    try:
        from pydub import AudioSegment
    except Exception as exc:
        from voice_studio.error_log import log_warning

        log_warning("export/mp3", f"pydub недоступний: {exc}")
        return None

    pcm16 = float_to_int16(audio)
    try:
        segment = AudioSegment(
            pcm16.tobytes(),
            frame_rate=sample_rate,
            sample_width=2,
            channels=1,
        )
        buf = io.BytesIO()
        segment.export(buf, format="mp3", bitrate=bitrate)
        return buf.getvalue()
    except Exception as exc:
        from voice_studio.error_log import log_warning

        log_warning("export/mp3", f"Не вдалося зібрати MP3 (WAV усе одно буде): {exc}")
        return None


def save_wav_file(path: str, sample_rate: int, audio: np.ndarray) -> str:
    with open(path, "wb") as f:
        f.write(to_wav_bytes(sample_rate, audio))
    return path


def save_mp3_file(path: str, sample_rate: int, audio: np.ndarray) -> str | None:
    data = to_mp3_bytes(sample_rate, audio)
    if data is None:
        return None
    with open(path, "wb") as f:
        f.write(data)
    return path
