"""Другий якісний офлайн-двигун — StyleTTS2 Ukrainian (patriotyk/styletts2-ukrainian).

Той самий рушій, що працює на
https://huggingface.co/spaces/patriotyk/styletts2-ukrainian — 30 дикторських
стилів голосу (значно більше за 5 голосів Robinhad) і керування темпом
мовлення. Через важкі та несумісні з .venv-robinhad залежності (окремі
версії torch/transformers) працює в ІЗОЛЬОВАНОМУ середовищі
`.venv-styletts2`, яке не заважає основній програмі чи Robinhad.

Модель і всі стилі тримаються "теплими" в довготривалому фоновому процесі
(engines/styletts2_worker.py), тому після першого (повільнішого) запуску
кожен наступний синтез — лише кілька секунд. Використовує GPU (CUDA)
автоматично, якщо він доступний — інакше CPU.

Встановлення (одноразово):
    tools\\setup_styletts2.ps1
(створює .venv-styletts2, ставить torch+styletts2-inference, завантажує
модель + 30 файлів стилів у models/styletts2/voices)
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

from voice_studio.config import STYLETTS2_VOICES_DIR, STYLETTS2_WORKER_SCRIPT, VENV_STYLETTS2_PYTHON

MARK = "@@JSON@@"
_START_TIMEOUT = 240.0
_REQUEST_TIMEOUT = 120.0

_lock = threading.Lock()
_proc: subprocess.Popen | None = None
_out_queue: "queue.Queue[str]" = queue.Queue()
_reader_thread: threading.Thread | None = None


def is_installed() -> bool:
    return VENV_STYLETTS2_PYTHON.exists() and STYLETTS2_WORKER_SCRIPT.exists()


def status_message() -> str:
    if not is_installed():
        return (
            "⚠️ StyleTTS2 (30 голосів) ще не встановлено. Запустіть один раз: "
            "tools\\setup_styletts2.ps1 (~15-25 хв, ~3-4 ГБ, потрібен інтернет)."
        )
    with _lock:
        running = _proc is not None and _proc.poll() is None
    if running:
        return "✅ StyleTTS2 завантажено і готовий (працює у фоні)."
    return "✅ Встановлено. Модель завантажиться в пам'ять при першому синтезі (10-40 с)."


def list_voices() -> list[str]:
    """Список імен стилів без запуску процесу (для наповнення dropdown у UI)."""
    if not STYLETTS2_VOICES_DIR.exists():
        return []
    return sorted(p.stem for p in STYLETTS2_VOICES_DIR.glob("*.pt"))


def _reader_loop(proc: subprocess.Popen) -> None:
    try:
        for raw_line in proc.stdout:
            if raw_line.startswith(MARK):
                _out_queue.put(raw_line[len(MARK):].strip())
    except Exception:
        pass


def _start_locked() -> None:
    global _proc, _reader_thread
    reader_alive = _reader_thread is not None and _reader_thread.is_alive()
    if _proc is not None and _proc.poll() is None and reader_alive:
        return
    if _proc is not None:
        _stop_locked()
    if not is_installed():
        raise RuntimeError(status_message())

    STYLETTS2_VOICES_DIR.mkdir(parents=True, exist_ok=True)
    child_env = dict(os.environ)
    child_env["PYTHONIOENCODING"] = "utf-8"
    child_env["PYTHONUTF8"] = "1"
    _proc = subprocess.Popen(
        [str(VENV_STYLETTS2_PYTHON), str(STYLETTS2_WORKER_SCRIPT), str(STYLETTS2_VOICES_DIR)],
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
            "Двигун StyleTTS2 не відповів за відведений час (перше завантаження "
            "моделі може тривати до кількох хвилин). Спробуйте ще раз."
        )
    msg = json.loads(raw)
    if not msg.get("ready"):
        _stop_locked()
        raise RuntimeError(f"Не вдалося запустити StyleTTS2:\n{msg.get('error', '?')}")


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
            raise RuntimeError("StyleTTS2 не відповів за відведений час.")
        return json.loads(raw)


def synthesize(text: str, voice: str, speed: float = 1.0) -> tuple[int, np.ndarray]:
    if not text.strip():
        raise ValueError("Порожній текст для синтезу.")

    work_dir = Path(tempfile.gettempdir()) / "voice_studio_styletts2"
    work_dir.mkdir(parents=True, exist_ok=True)
    output_wav = work_dir / f"{uuid.uuid4().hex}.wav"

    result = _send_request({
        "text": text,
        "voice": voice,
        "speed": speed,
        "output_wav": str(output_wav),
    })
    if not result.get("ok"):
        raise RuntimeError(f"Помилка синтезу StyleTTS2: {result.get('error', 'невідома помилка')}")

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
