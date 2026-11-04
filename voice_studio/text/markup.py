"""Простий тег-синтаксис керування озвучкою прямо в тексті.

Підтримувані теги (регістр не важливий, укр. та англ. назви — синоніми):

  [повільно] ... [/повільно]  — локально повільніше мовлення
  [slow] ... [/slow]

  [швидко] ... [/швидко]      — локально швидше мовлення
  [fast] ... [/fast]

  [пауза 0.5]  або  [пауза=0.5]  або  [pause:0.5]
                               — вставляє тишу тривалістю 0.5 секунди

Наголос ("+" перед голосною) обробляється окремо в text/stress.py і працює
всередині будь-якого сегмента.

Приклад:
  "Це звичайний текст. [пауза=1] Далі далі, [швидко]а тут швидше[/швидко]."
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_TAG_RE = re.compile(
    r"\[\s*(/?)\s*(повільно|slow|швидко|fast|пауза|pause)"
    r"(?:\s*[:=]?\s*([\d]+(?:[.,]\d+)?))?\s*\]",
    re.IGNORECASE,
)

_SLOW_TAGS = {"повільно", "slow"}
_FAST_TAGS = {"швидко", "fast"}
_PAUSE_TAGS = {"пауза", "pause"}

SLOW_RATE_MULT = 1.35
FAST_RATE_MULT = 0.78


@dataclass
class Segment:
    kind: str  # "speech" | "pause"
    text: str = ""
    rate_mult: float = 1.0
    seconds: float = 0.0


@dataclass
class _State:
    rate: str = "normal"  # normal | slow | fast


def parse_markup(text: str) -> list[Segment]:
    """Розбирає текст із тегами на список сегментів мовлення/пауз."""
    segments: list[Segment] = []
    state = _State()
    pos = 0

    def flush(chunk: str) -> None:
        if not chunk:
            return
        rate_mult = SLOW_RATE_MULT if state.rate == "slow" else (
            FAST_RATE_MULT if state.rate == "fast" else 1.0
        )
        segments.append(Segment(kind="speech", text=chunk, rate_mult=rate_mult))

    for m in _TAG_RE.finditer(text):
        chunk = text[pos:m.start()]
        flush(chunk)
        pos = m.end()

        closing = m.group(1) == "/"
        tag = m.group(2).lower()
        value = m.group(3)

        if tag in _SLOW_TAGS:
            state.rate = "normal" if closing else "slow"
        elif tag in _FAST_TAGS:
            state.rate = "normal" if closing else "fast"
        elif tag in _PAUSE_TAGS:
            try:
                seconds = float((value or "0.4").replace(",", "."))
            except ValueError:
                seconds = 0.4
            segments.append(Segment(kind="pause", seconds=max(0.0, min(seconds, 10.0))))

    flush(text[pos:])
    return [s for s in segments if s.kind == "pause" or s.text.strip()]


def strip_markup(text: str) -> str:
    """Прибирає теги розмітки, залишаючи чистий текст (для попереднього
    перегляду / підрахунку символів)."""
    return _TAG_RE.sub("", text)
