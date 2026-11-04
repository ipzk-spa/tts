"""Дедуплікація RVC-завантажень за SHA-256."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from voice_studio.models_manager import save_rvc_files


def test_save_rvc_dedup_by_hash(tmp_path, monkeypatch):
    uploads = tmp_path / "rvc"
    uploads.mkdir()
    monkeypatch.setattr("voice_studio.models_manager.RVC_UPLOADS_DIR", uploads)
    monkeypatch.setattr(
        "voice_studio.models_manager._HASH_INDEX",
        uploads / ".hash_index.json",
    )

    src1 = tmp_path / "voice.pth"
    src1.write_bytes(b"fake-rvc-weights-abc")
    path1, _, msg1 = save_rvc_files(str(src1), None, pth_original_name="My_voice.pth")
    assert Path(path1).is_file()
    assert "дублікат" not in msg1.lower()

    src2 = tmp_path / "copy.pth"
    src2.write_bytes(b"fake-rvc-weights-abc")  # той самий вміст
    path2, _, msg2 = save_rvc_files(str(src2), None, pth_original_name="Other_name.pth")
    assert path2 == path1
    assert "дублікат" in msg2.lower() or "вже" in msg2.lower()
    assert len(list(uploads.glob("*.pth"))) == 1
