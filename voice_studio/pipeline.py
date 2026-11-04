"""Оркестрація конвеєра синтезу з колбеком прогресу для UI."""
from __future__ import annotations

import tempfile
import uuid
from collections.abc import Callable
from pathlib import Path

import numpy as np
import soundfile as sf

from voice_studio.audio.effects import make_silence, normalize_peak
from voice_studio.engines import robinhad_engine, rvc_engine, styletts2_engine
from voice_studio.text.chunking import split_into_sentences
from voice_studio.text.markup import parse_markup
from voice_studio.text.stress import preview_accented
from voice_studio.text.verbalizer import verbalize_text

ProgressCb = Callable[[dict], None]

# Менші паузи між реченнями — менше «нарізки», природніший потік.
_GAP_SECONDS = 0.04
_SENTENCE_GAP_ROBINHAD = 0.06
_SENTENCE_GAP_STYLETTS2 = 0.10
_ROBINHAD_MAX_CHARS = 420  # довші фрази = краща просодія


def _emit(cb: ProgressCb | None, **payload) -> None:
    if cb is not None:
        cb(payload)


def preview_verbalize(text: str) -> str:
    if not text.strip():
        return text

    segments = parse_markup(text)
    if not segments:
        return text

    parts: list[str] = []
    for seg in segments:
        if seg.kind == "pause":
            parts.append(f"[пауза={seg.seconds:g}]")
            continue
        verbalized = verbalize_text(seg.text)
        if seg.rate_mult > 1.0:
            parts.append(f"[повільно]{verbalized}[/повільно]")
        elif seg.rate_mult < 1.0:
            parts.append(f"[швидко]{verbalized}[/швидко]")
        else:
            parts.append(verbalized)
    return " ".join(parts)


def preview_stress(text: str, mode: str = "auto") -> str:
    """Показує автонаголос у вигляді `+` перед голосними (як у довідці)."""
    if not text.strip():
        return text

    segments = parse_markup(text)
    if not segments:
        return preview_accented(text, mode)

    parts: list[str] = []
    for seg in segments:
        if seg.kind == "pause":
            parts.append(f"[пауза={seg.seconds:g}]")
            continue
        accented = preview_accented(seg.text, mode)
        if seg.rate_mult > 1.0:
            parts.append(f"[повільно]{accented}[/повільно]")
        elif seg.rate_mult < 1.0:
            parts.append(f"[швидко]{accented}[/швидко]")
        else:
            parts.append(accented)
    return " ".join(parts)


def _collect_speech_chunks(
    text: str,
    do_verbalize: bool,
    max_chars: int,
) -> tuple[list[tuple[str, str, float]], list[str]]:
    """Повертає (робота: pause|speech, текст/сек, rate), preview_parts."""
    segments = parse_markup(text)
    if not segments:
        raise ValueError("Після розбору розмітки текст порожній.")

    jobs: list[tuple[str, str, float]] = []
    preview_parts: list[str] = []

    for seg in segments:
        if seg.kind == "pause":
            jobs.append(("pause", str(seg.seconds), 1.0))
            continue
        chunk_text = verbalize_text(seg.text) if do_verbalize else seg.text
        preview_parts.append(chunk_text)
        for sentence in split_into_sentences(chunk_text, max_chars=max_chars):
            jobs.append(("speech", sentence, seg.rate_mult))

    return jobs, preview_parts


def synthesize_robinhad(
    text: str,
    voice: str,
    do_verbalize: bool = True,
    threshold: float = 0.5,
    maxlenratio: float = 10.0,
    use_att_constraint: bool = False,
    stress_mode: str = "model",
    on_progress: ProgressCb | None = None,
) -> tuple[int, np.ndarray, str]:
    if not text.strip():
        raise ValueError("Введіть текст для озвучки.")

    # Кастомний decode лише якщо користувач зсунув дефолти стабільності.
    use_custom_decode = (
        abs(threshold - 0.5) > 1e-6
        or abs(maxlenratio - 10.0) > 1e-6
        or use_att_constraint
    )

    jobs, preview_parts = _collect_speech_chunks(
        text, do_verbalize, max_chars=_ROBINHAD_MAX_CHARS
    )
    speech_total = sum(1 for kind, _, _ in jobs if kind == "speech")
    if speech_total == 0:
        raise ValueError("Не вдалося синтезувати жодного фрагмента.")

    _emit(
        on_progress,
        type="progress",
        phase="tts",
        current=0,
        total=speech_total,
        message=f"Підготовка Robinhad… фрагментів: {speech_total}",
    )

    audio_parts: list[np.ndarray] = []
    sample_rate = 22050
    gap = make_silence(_GAP_SECONDS, sample_rate)
    sentence_gap = make_silence(_SENTENCE_GAP_ROBINHAD, sample_rate)
    done = 0

    for kind, payload, _rate in jobs:
        if kind == "pause":
            audio_parts.append(make_silence(float(payload), sample_rate))
            continue

        done += 1
        _emit(
            on_progress,
            type="progress",
            phase="tts",
            current=done,
            total=speech_total,
            message=f"Синтез {done}/{speech_total}: {payload[:48]}…",
        )
        sr, audio = robinhad_engine.synthesize(
            payload,
            voice,
            threshold=threshold,
            maxlenratio=maxlenratio,
            use_att_constraint=use_att_constraint,
            stress_mode=stress_mode,
            use_custom_decode=use_custom_decode,
        )
        sample_rate = sr
        if gap.size == 0 or len(gap) != int(_GAP_SECONDS * sample_rate):
            gap = make_silence(_GAP_SECONDS, sample_rate)
            sentence_gap = make_silence(_SENTENCE_GAP_ROBINHAD, sample_rate)

        if audio_parts and not (len(audio_parts) == 1 and audio_parts[0].size == 0):
            # Пауза між сусідніми мовними фрагментами (не перед першим).
            if done > 1:
                audio_parts.append(sentence_gap)
        audio_parts.append(audio)

    audio_parts.append(gap)
    final_audio = normalize_peak(np.concatenate(audio_parts), target=0.95)
    return sample_rate, final_audio, " ".join(preview_parts)


def synthesize_styletts2(
    text: str,
    voice: str,
    speed: float = 1.0,
    do_verbalize: bool = True,
    on_progress: ProgressCb | None = None,
) -> tuple[int, np.ndarray, str]:
    if not text.strip():
        raise ValueError("Введіть текст для озвучки.")

    jobs, preview_parts = _collect_speech_chunks(text, do_verbalize, max_chars=280)
    speech_total = sum(1 for kind, _, _ in jobs if kind == "speech")
    if speech_total == 0:
        raise ValueError("Не вдалося синтезувати жодного фрагмента.")

    _emit(
        on_progress,
        type="progress",
        phase="tts",
        current=0,
        total=speech_total,
        message=f"Підготовка StyleTTS2… фрагментів: {speech_total}",
    )

    audio_parts: list[np.ndarray] = []
    sample_rate = 24000
    gap = make_silence(_GAP_SECONDS, sample_rate)
    sentence_gap = make_silence(_SENTENCE_GAP_STYLETTS2, sample_rate)
    done = 0

    for kind, payload, rate_mult in jobs:
        if kind == "pause":
            audio_parts.append(make_silence(float(payload), sample_rate))
            continue

        done += 1
        seg_speed = max(0.7, min(1.3, speed * rate_mult))
        _emit(
            on_progress,
            type="progress",
            phase="tts",
            current=done,
            total=speech_total,
            message=f"Синтез {done}/{speech_total}: {payload[:48]}…",
        )
        sr, audio = styletts2_engine.synthesize(payload, voice, speed=seg_speed)
        sample_rate = sr
        if gap.size == 0 or len(gap) != int(_GAP_SECONDS * sample_rate):
            gap = make_silence(_GAP_SECONDS, sample_rate)
            sentence_gap = make_silence(_SENTENCE_GAP_STYLETTS2, sample_rate)
        if done > 1:
            audio_parts.append(sentence_gap)
        audio_parts.append(audio)

    audio_parts.append(gap)
    final_audio = normalize_peak(np.concatenate(audio_parts), target=0.95)
    return sample_rate, final_audio, " ".join(preview_parts)


def revoice_with_rvc(
    sr: int,
    audio: np.ndarray,
    model_path: str,
    index_path: str = "",
    f0_method: str = "rmvpe",
    index_rate: float = 0.75,
    pitch: int = 0,
    on_progress: ProgressCb | None = None,
) -> tuple[int, np.ndarray]:
    _emit(
        on_progress,
        type="progress",
        phase="rvc",
        current=0,
        total=1,
        message="RVC: переозвучення власною моделлю…",
    )
    work_dir = Path(tempfile.gettempdir()) / "voice_studio_hybrid"
    work_dir.mkdir(parents=True, exist_ok=True)
    src_wav = work_dir / f"{uuid.uuid4().hex}.wav"
    sf.write(str(src_wav), audio, sr)

    try:
        out_sr, out_audio = rvc_engine.convert_audio(
            input_wav=str(src_wav),
            model_path=model_path,
            index_path=index_path,
            f0_method=f0_method,
            index_rate=index_rate,
            pitch=pitch,
        )
    finally:
        try:
            src_wav.unlink(missing_ok=True)
        except Exception:
            pass

    _emit(
        on_progress,
        type="progress",
        phase="rvc",
        current=1,
        total=1,
        message="RVC: готово",
    )
    return out_sr, normalize_peak(out_audio, target=0.95)
