"""Розбиття довгого тексту на речення перед відправкою у TTS-рушій.

Обов'язково для StyleTTS2: його модуль наголосу/просодії (ALBERT) має
жорсткий ліміт ~512 токенів — цілий абзац чи довга історія (як пост із
соцмережі) перевищує його і рушій падає з помилкою "expanded size of the
tensor must match...". Для Robinhad жорсткого ліміту немає, але дуже довгий
шматок тексту за раз також погіршує природність (більше шансів на
обрізання/дрейф інтонації), тому розбиття корисне для обох рушіїв.

Викликати ПІСЛЯ вербалізації (щоб крапки в датах/числах типу "24.08.1991"
уже перетворились на слова і не плутались із межами речень)."""
from __future__ import annotations

import re

_SENTENCE_END_RE = re.compile(r"(?<=[.!?…:])\s+")
_MAX_CHARS_DEFAULT = 280


def split_into_sentences(text: str, max_chars: int = _MAX_CHARS_DEFAULT) -> list[str]:
    """Групує текст у речення, зливаючи короткі сусідні речення разом
    (до max_chars), і твердо розрізає лише аномально довгі речення без
    розділових знаків (по словах), щоб жоден шматок не перевищував ліміт."""
    text = text.strip()
    if not text:
        return []

    raw_sentences = [s.strip() for s in _SENTENCE_END_RE.split(text) if s.strip()]
    if not raw_sentences:
        raw_sentences = [text]

    chunks: list[str] = []
    buf = ""

    def flush_buf() -> None:
        nonlocal buf
        if buf:
            chunks.append(buf.strip())
            buf = ""

    for sentence in raw_sentences:
        if len(sentence) > max_chars:
            flush_buf()
            words = sentence.split(" ")
            sub = ""
            for word in words:
                candidate = f"{sub} {word}".strip()
                if len(candidate) > max_chars and sub:
                    chunks.append(sub.strip())
                    sub = word
                else:
                    sub = candidate
            if sub:
                chunks.append(sub.strip())
            continue

        candidate = f"{buf} {sentence}".strip()
        if len(candidate) <= max_chars:
            buf = candidate
        else:
            flush_buf()
            buf = sentence

    flush_buf()
    return chunks or [text]
