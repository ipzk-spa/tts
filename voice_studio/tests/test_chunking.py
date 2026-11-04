"""Тести розбиття тексту на речення."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from voice_studio.text.chunking import split_into_sentences


def test_split_short_sentences():
    text = "Перше речення. Друге речення. Третє."
    chunks = split_into_sentences(text, max_chars=280)
    assert len(chunks) >= 1
    assert all(len(c) <= 280 for c in chunks)


def test_split_long_without_punctuation():
    words = " ".join(["слово"] * 80)
    chunks = split_into_sentences(words, max_chars=100)
    assert len(chunks) > 1
    assert all(len(c) <= 100 for c in chunks)


def test_empty():
    assert split_into_sentences("") == []
    assert split_into_sentences("   ") == []
