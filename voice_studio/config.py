"""Шляхи та константи для Spag Voice Studio (SVS+).

Усе живе всередині робочої папки проєкту — програма не виходить за її межі.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MODELS_DIR = ROOT / "models"
ROBINHAD_DIR = MODELS_DIR / "robinhad"
STYLETTS2_DIR = MODELS_DIR / "styletts2"
STYLETTS2_VOICES_DIR = STYLETTS2_DIR / "voices"
UPLOADS_DIR = MODELS_DIR / "uploads"
RVC_UPLOADS_DIR = UPLOADS_DIR / "rvc"

OUTPUT_DIR = ROOT / "voice_studio" / "outputs"
LOGS_DIR = ROOT / "logs"

VENV_RVC_PYTHON = ROOT / ".venv-rvc" / "Scripts" / "python.exe"
RVC_WORKER_SCRIPT = ROOT / "voice_studio" / "engines" / "rvc_worker.py"

VENV_ROBINHAD_PYTHON = ROOT / ".venv-robinhad" / "Scripts" / "python.exe"
ROBINHAD_WORKER_SCRIPT = ROOT / "voice_studio" / "engines" / "robinhad_worker.py"

VENV_STYLETTS2_PYTHON = ROOT / ".venv-styletts2" / "Scripts" / "python.exe"
STYLETTS2_WORKER_SCRIPT = ROOT / "voice_studio" / "engines" / "styletts2_worker.py"

for _d in (
    MODELS_DIR,
    ROBINHAD_DIR,
    STYLETTS2_DIR,
    STYLETTS2_VOICES_DIR,
    UPLOADS_DIR,
    RVC_UPLOADS_DIR,
    OUTPUT_DIR,
    LOGS_DIR,
):
    _d.mkdir(parents=True, exist_ok=True)

APP_TITLE = "Spag Voice Studio"
APP_SHORT = "SVS+"
APP_LOGO = "SVS+"
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 7900

# Орієнтовні секунди на фрагмент (для ETA в UI); GPU суттєво швидший.
ETA_SEC_PER_CHUNK_GPU = {"robinhad": 2.5, "styletts2": 3.0, "rvc": 4.0}
ETA_SEC_PER_CHUNK_CPU = {"robinhad": 12.0, "styletts2": 15.0, "rvc": 20.0}
