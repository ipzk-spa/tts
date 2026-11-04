"""Керування наголосом: ручний ("+" перед голосною) та автоматичний.

Внутрішній формат наголосу — голосна літера + символ, що йде відразу після
неї, U+0301 (combining acute accent) — той самий, що використовує бібліотека
ukrainian_word_stress (і, відповідно, Robinhad/StyleTTS2 під капотом).

Користувач же вводить наголос звичним для української TTS-спільноти способом:
знак "+" ПЕРЕД наголошеною голосною, напр. "прив+іт". Ця функція перетворює
такий запис у внутрішній формат з U+0301 і залишає решту слів для
автоматичного наголошувача (ukrainian_word_stress), який не чіпає вже
позначені слова.
"""
from __future__ import annotations

import re

try:
    from ukrainian_word_stress import Stressifier, StressSymbol

    _stressify = Stressifier(stress_symbol=StressSymbol.CombiningAcuteAccent)
    AUTO_STRESS_AVAILABLE = True
except Exception:  # pragma: no cover - пакет не встановлено
    _stressify = None
    AUTO_STRESS_AVAILABLE = False

COMBINING_ACUTE = "\u0301"
_VOWELS = "аеєиіїоуюяАЕЄИІЇОУЮЯ"

_PLUS_STRESS_RE = re.compile(rf"\+([{_VOWELS}])")


def apply_manual_marks(text: str) -> str:
    """Перетворює "+голосна" на "голосна + U+0301" (внутрішній формат)."""
    return _PLUS_STRESS_RE.sub(lambda m: m.group(1) + COMBINING_ACUTE, text)


def apply_stress(text: str, mode: str = "auto") -> str:
    """Застосовує наголос до тексту.

    mode:
      "auto"   — ручні позначення "+" (пріоритет) + авто-наголос словником
                 для решти слів.
      "manual" — лише ручні позначення "+", інші слова без наголосу
                 (модель сама вирішить наголос).
      "none"   — наголос не застосовується взагалі (наголос вирішує модель).
    """
    text = apply_manual_marks(text)
    # Прибираємо будь-які залишкові "+" (користувач поставив не перед
    # голосною) — інакше символ заплутає словник наголосів і саму модель.
    text = text.replace("+", "")

    if mode == "none":
        return text.replace(COMBINING_ACUTE, "")
    if mode == "manual" or not AUTO_STRESS_AVAILABLE:
        return text
    try:
        return _stressify(text)
    except Exception:
        return text


def acute_to_plus(text: str) -> str:
    """U+0301 після голосної → `+` перед голосною (для показу в полі тексту)."""
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if i + 1 < n and text[i + 1] == COMBINING_ACUTE and ch in _VOWELS:
            out.append("+")
            out.append(ch)
            i += 2
            continue
        if ch == COMBINING_ACUTE:
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def preview_accented(text: str, mode: str = "auto") -> str:
    """Наголошений текст у вигляді з `+` перед голосними (як у довідці)."""
    return acute_to_plus(apply_stress(text, mode))
