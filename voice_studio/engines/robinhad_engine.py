"""Найякісніший офлайн-двигун — robinhad/ukrainian-tts (ESPnet Tacotron2 + HiFiGAN).

Це той самий рушій, що працює на https://huggingface.co/spaces/robinhad/ukrainian-tts
— навчений саме на дикторських якісних українських голосах (Тетяна, Микита,
Лада, Дмитро, Олекса), звучить набагато природніше за легкі генеричні рушії.
Через важкі залежності (torch + espnet, кілька ГБ) працює в ІЗОЛЬОВАНОМУ
середовищі `.venv-robinhad`, яке не заважає основній програмі. Використовує
GPU (CUDA) автоматично, якщо він доступний — інакше CPU.

Модель тримається "теплою" в довготривалому фоновому процесі
(engines/robinhad_worker.py), тому після першого (повільнішого) запуску
кожен наступний синтез — лише кілька секунд.

Наголос: пріоритет ручних позначок "+" перед голосною (напр. "прив+іт"),
для решти слів — автоматичний словниковий наголос. Це вбудовано в сам
рушій (та саму бібліотеку ukrainian-word-stress, що й наш text/stress.py).

Встановлення (одноразово):
    tools\\setup_robinhad.ps1
(створює .venv-robinhad, ставить torch+espnet+ukrainian-tts, завантажує
~430 МБ моделі у models/robinhad)
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import tempfile
import threading
import uuid
from pathlib import Path

import numpy as np
import soundfile as sf

from voice_studio.config import ROBINHAD_DIR, ROBINHAD_WORKER_SCRIPT, VENV_ROBINHAD_PYTHON

VOICES = [
    ("Тетяна (жіночий)", "tetiana"),
    ("Микита (чоловічий)", "mykyta"),
    ("Лада (жіночий)", "lada"),
    ("Дмитро (чоловічий)", "dmytro"),
    ("Олекса (чоловічий)", "oleksa"),
]

MARK = "@@JSON@@"
_START_TIMEOUT = 180.0
_REQUEST_TIMEOUT = 120.0

_lock = threading.Lock()
_proc: subprocess.Popen | None = None
_out_queue: "queue.Queue[str]" = queue.Queue()
_reader_thread: threading.Thread | None = None
_device = "unknown"


def is_installed() -> bool:
    return VENV_ROBINHAD_PYTHON.exists() and ROBINHAD_WORKER_SCRIPT.exists()


def status_message() -> str:
    if not is_installed():
        return (
            "⚠️ Найякісніший голос ще не встановлено. Запустіть один раз: "
            "tools\\setup_robinhad.ps1 (~10-20 хв, ~2 ГБ, потрібен інтернет)."
        )
    with _lock:
        running = _proc is not None and _proc.poll() is None
    if running:
        return "✅ Найякісніший голос завантажено і готовий (працює у фоні)."
    return "✅ Встановлено. Модель завантажиться в пам'ять при першому синтезі (10-30 с)."


def _reader_loop(proc: subprocess.Popen) -> None:
    # Worker пише службові рядки з префіксом MARK; errors="replace" на Popen
    # захищає від зламаного UTF-8 у сторонніх логах torch/espnet.
    try:
        for raw_line in proc.stdout:
            if raw_line.startswith(MARK):
                _out_queue.put(raw_line[len(MARK):].strip())
    except Exception:
        pass


def _start_locked() -> None:
    global _proc, _reader_thread, _device
    reader_alive = _reader_thread is not None and _reader_thread.is_alive()
    if _proc is not None and _proc.poll() is None and reader_alive:
        return
    if _proc is not None:
        # Reader помер або процес у неконсистентному стані — повний рестарт.
        _stop_locked()
    if not is_installed():
        raise RuntimeError(status_message())

    ROBINHAD_DIR.mkdir(parents=True, exist_ok=True)
    child_env = dict(os.environ)
    child_env["PYTHONIOENCODING"] = "utf-8"
    child_env["PYTHONUTF8"] = "1"
    _proc = subprocess.Popen(
        [str(VENV_ROBINHAD_PYTHON), str(ROBINHAD_WORKER_SCRIPT), str(ROBINHAD_DIR)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=child_env,
        bufsize=1,
    )
    _out_queue.queue.clear()
    _reader_thread = threading.Thread(target=_reader_loop, args=(_proc,), daemon=True)
    _reader_thread.start()

    try:
        raw = _out_queue.get(timeout=_START_TIMEOUT)
    except queue.Empty:
        _stop_locked()
        raise RuntimeError(
            "Двигун не відповів за відведений час (перше завантаження моделі "
            "може тривати до кількох хвилин на слабких ПК). Спробуйте ще раз."
        )
    msg = json.loads(raw)
    if not msg.get("ready"):
        _stop_locked()
        raise RuntimeError(f"Не вдалося запустити найякісніший голос:\n{msg.get('error', '?')}")

    _device = str(msg.get("device", "unknown"))


def _stop_locked() -> None:
    global _proc
    if _proc is not None:
        try:
            _proc.kill()
        except Exception:
            pass
    _proc = None


def _send_request(payload: dict) -> dict:
    with _lock:
        _start_locked()
        assert _proc is not None and _proc.stdin is not None
        try:
            _proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
            _proc.stdin.flush()
        except Exception:
            _stop_locked()
            _start_locked()
            assert _proc is not None and _proc.stdin is not None
            _proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
            _proc.stdin.flush()

        try:
            raw = _out_queue.get(timeout=_REQUEST_TIMEOUT)
        except queue.Empty:
            _stop_locked()
            raise RuntimeError("Найякісніший голос не відповів за відведений час.")
        return json.loads(raw)


def device_name() -> str:
    """cuda / cpu після першого старту worker; інакше unknown / n/a."""
    if not is_installed():
        return "n/a"
    return _device


def synthesize(
    text: str,
    voice: str = "tetiana",
    threshold: float = 0.5,
    maxlenratio: float = 10.0,
    use_att_constraint: bool = False,
    stress_mode: str = "model",
    use_custom_decode: bool = False,
) -> tuple[int, np.ndarray]:
    """Синтез. За замовчуванням — наголос моделі (як у HF-демо) і дефолти
    decode synthesizer (без кастомного decode_conf), щоб голос був природнішим."""
    if not text.strip():
        raise ValueError("Порожній текст для синтезу.")

    work_dir = Path(tempfile.gettempdir()) / "voice_studio_robinhad"
    work_dir.mkdir(parents=True, exist_ok=True)
    output_wav = work_dir / f"{uuid.uuid4().hex}.wav"

    result = _send_request({
        "text": text,
        "voice": voice,
        "output_wav": str(output_wav),
        "threshold": threshold,
        "maxlenratio": maxlenratio,
        "use_att_constraint": use_att_constraint,
        "stress_mode": stress_mode,
        "use_custom_decode": use_custom_decode,
    })
    if not result.get("ok"):
        raise RuntimeError(f"Помилка синтезу: {result.get('error', 'невідома помилка')}")

    data, sr = sf.read(str(output_wav), dtype="float32")
    if data.ndim > 1:
        data = data.mean(axis=1)

    try:
        output_wav.unlink(missing_ok=True)
    except Exception:
        pass

    return int(sr), data


def shutdown() -> None:
    with _lock:
        _stop_locked()
