"""Тести API Spag Voice Studio (SVS+) (FastAPI TestClient)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from voice_studio.api_server import app
from voice_studio.audio.export import to_wav_bytes
from voice_studio.config import OUTPUT_DIR


@pytest.fixture
def client():
    return TestClient(app)


def test_index_returns_html(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    assert "Spag Voice Studio" in r.text
    assert "SVS+" in r.text


def test_static_css(client):
    r = client.get("/css/studio.css")
    assert r.status_code == 200
    assert "studio-gold" in r.text


def test_static_js(client):
    r = client.get("/js/app.js")
    assert r.status_code == 200
    assert "onSynthesize" in r.text


def test_api_status(client):
    r = client.get("/api/status")
    assert r.status_code == 200
    data = r.json()
    assert "robinhad" in data
    assert "styletts2" in data
    assert "rvc" in data
    assert data["default_engine"] in ("robinhad", "styletts2")


def test_api_verbalize(client):
    r = client.post("/api/verbalize", json={"text": "Зустріч 24.08.1991 о 14:30."})
    assert r.status_code == 200
    data = r.json()
    assert "двадцять" in data["text"].lower() or "четверт" in data["text"].lower()


def test_api_stress(client):
    r = client.post("/api/stress", json={"text": "привіт світе", "mode": "auto"})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data["text"], str)
    assert len(data["text"]) >= len("привіт світе") - 2


def test_api_synthesize_mock_robinhad(client):
    fake_audio = np.zeros(2205, dtype=np.float32)

    with patch("voice_studio.api_server.pipeline.synthesize_robinhad") as mock_syn:
        mock_syn.return_value = (22050, fake_audio, "preview text")
        r = client.post(
            "/api/synthesize",
            json={
                "engine": "robinhad",
                "text": "Привіт.",
                "robinhad_voice": "tetiana",
            },
        )

    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["wav_url"].startswith("/api/download/")
    assert data["wav_filename"].endswith(".wav")
    assert (OUTPUT_DIR / data["wav_filename"]).is_file()


def test_api_synthesize_error(client):
    with patch("voice_studio.api_server.pipeline.synthesize_robinhad") as mock_syn:
        mock_syn.side_effect = ValueError("Тестова помилка")
        r = client.post(
            "/api/synthesize",
            json={"engine": "robinhad", "text": ""},
        )

    data = r.json()
    assert data["ok"] is False
    assert "Тестова помилка" in data["status"]


def test_api_download_wav(client):
    name = "_test_download.wav"
    path = OUTPUT_DIR / name
    path.write_bytes(to_wav_bytes(22050, np.zeros(100, dtype=np.float32)))
    try:
        r = client.get(f"/api/download/{name}")
        assert r.status_code == 200
        assert r.headers.get("content-disposition", "").find(name) >= 0
        assert len(r.content) > 44
    finally:
        path.unlink(missing_ok=True)


def test_api_download_rejects_traversal(client):
    r = client.get("/api/download/..%2F..%2Fetc%2Fpasswd")
    assert r.status_code in (400, 404, 403)


def test_api_download_missing(client):
    r = client.get("/api/download/nonexistent_file_xyz.wav")
    assert r.status_code == 404
