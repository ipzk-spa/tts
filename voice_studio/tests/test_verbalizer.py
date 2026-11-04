"""Тести вербалізації."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from voice_studio.pipeline import preview_verbalize
from voice_studio.text.verbalizer import verbalize_text


def test_verbalize_date():
    out = verbalize_text("Зустріч 24.08.1991 о 14:30.")
    assert "24" not in out or "двадцять" in out.lower()
    assert "14:30" not in out


def test_verbalize_preview_keeps_markup():
    text = "[пауза=0.5] Зустріч 24.08.1991."
    out = preview_verbalize(text)
    assert "[пауза=0.5]" in out
    assert "24.08.1991" not in out
