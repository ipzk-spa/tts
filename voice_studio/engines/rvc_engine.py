"""RVC-двигун (голос користувача: .pth + .index) — опційний.

Використовується лише в гібридному режимі: `convert_audio()` переозвучує
вже готовий WAV (з Robinhad/StyleTTS2) вашою моделлю — "найкращий TTS читає,
RVC надає тембр". Через важкі та хиткі на Windows залежності (fairseq,
torch, faiss) RVC
працює в ІЗОЛЬОВАНОМУ віртуальному середовищі `.venv-rvc`, яке не заважає
основній програмі. Спілкування з ним відбувається через окремий процес
(engines/rvc_worker.py) і JSON-файли — якщо середовище відсутнє чи щось
пішло не так, програма просто показує зрозуміле повідомлення й решта
рушіїв продовжують працювати без збоїв.

Встановлення (одноразово, за бажанням):
    tools\\setup_rvc.ps1
(створює .venv-rvc і ставить tts-with-rvc + fairseq-built + edge-tts)
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import uuid
from pathlib import Path

import numpy as np
import soundfile as sf

from voice_studio.config import RVC_WORKER_SCRIPT, VENV_RVC_PYTHON

F0_METHODS = ["rmvpe", "pm", "harvest", "crepe", "dio"]


def is_available() -> bool:
    return VENV_RVC_PYTHON.exists() and RVC_WORKER_SCRIPT.exists()


def status_message() -> str:
    if is_available():
        return "✅ RVC-середовище знайдено (.venv-rvc) — можна використовувати власну модель."
    return (
        "⚠️ RVC не встановлено. Запустіть один раз: tools\\setup_rvc.ps1 "
        "(створить окреме середовище, ~5-10 хв, потрібен інтернет)."
    )


def convert_audio(
    input_wav: str,
    model_path: str,
    index_path: str = "",
    f0_method: str = "rmvpe",
    index_rate: float = 0.75,
    pitch: int = 0,
    timeout: int = 300,
) -> tuple[int, np.ndarray]:
    """Переозвучує вже готовий WAV (напр. з Robinhad чи StyleTTS2) вашою
    RVC-моделлю — гібридний режим, викликається з pipeline.revoice_with_rvc."""
    if not is_available():
        raise RuntimeError(status_message())
    if not model_path or not Path(model_path).exists():
        raise RuntimeError("Оберіть файл моделі .pth")
    if not input_wav or not Path(input_wav).exists():
        raise RuntimeError("Базовий аудіофайл для переозвучення не знайдено.")

    work_dir = Path(tempfile.gettempdir()) / "voice_studio_rvc"
    work_dir.mkdir(parents=True, exist_ok=True)
    uid = uuid.uuid4().hex
    output_wav = work_dir / f"{uid}_out.wav"

    request = {
        "mode": "convert_audio",
        "model_path": str(model_path),
        "index_path": str(index_path) if index_path else "",
        "input_wav": str(input_wav),
        "f0_method": f0_method,
        "index_rate": index_rate,
        "pitch": pitch,
        "output_wav": str(output_wav),
    }
    return _run_worker(request, work_dir, uid, timeout)


def _run_worker(request: dict, work_dir: Path, uid: str, timeout: int) -> tuple[int, np.ndarray]:
    request_path = work_dir / f"{uid}.json"
    result_path = work_dir / f"{uid}.result.json"
    request_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")

    child_env = dict(os.environ)
    child_env["PYTHONIOENCODING"] = "utf-8"
    child_env["PYTHONUTF8"] = "1"
    # ffmpeg для RVC load_audio — беремо з основного .venv (imageio-ffmpeg)
    try:
        import imageio_ffmpeg

        ffmpeg_dir = str(Path(imageio_ffmpeg.get_ffmpeg_exe()).parent)
        child_env["PATH"] = ffmpeg_dir + os.pathsep + child_env.get("PATH", "")
    except Exception:
        pass

    proc = subprocess.run(
        [str(VENV_RVC_PYTHON), str(RVC_WORKER_SCRIPT), str(request_path)],
        capture_output=True,
        timeout=timeout,
        env=child_env,
    )

    if not result_path.exists():
        stderr = proc.stderr.decode("utf-8", errors="ignore")
        raise RuntimeError(f"RVC-процес не повернув результат.\n{stderr[-2000:]}")

    result = json.loads(result_path.read_text(encoding="utf-8"))
    if not result.get("ok"):
        raise RuntimeError(f"RVC помилка: {result.get('error', 'невідома помилка')}")

    data, sr = sf.read(result["output_wav"], dtype="float32")
    if data.ndim > 1:
        data = data.mean(axis=1)
    return int(sr), data
