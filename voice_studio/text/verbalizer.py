"""Вербалізація українського тексту: цифри, дати, час, скорочення.

Ціль — привести "сирий" текст у форму, яку природно вимовляє TTS-модель:
* числа -> слова ("125" -> "сто двадцять п'ять")
* дати "24.08.1991" -> "двадцять четверте серпня тисяча дев'ятсот дев'яносто
  першого року"
* час "14:30" -> "чотирнадцять годин тридцять хвилин"
* поширені скорочення та абревіатури -> повні слова / буквене прочитання
"""
from __future__ import annotations

import re

from num2words import num2words

_MONTHS_GENITIVE = {
    1: "січня", 2: "лютого", 3: "березня", 4: "квітня", 5: "травня",
    6: "червня", 7: "липня", 8: "серпня", 9: "вересня", 10: "жовтня",
    11: "листопада", 12: "грудня",
}

def _last_word_to_neuter(phrase: str) -> str:
    """Масчинний називний відмінок порядкового числівника -> середній
    (потрібен для дня місяця: "число" — середнього роду).
    "третій" -> "третє", "четвертий" -> "четверте", "перший" -> "перше"."""
    words = phrase.rsplit(" ", 1)
    last = words[-1]
    if last.endswith("ій"):
        last = last[:-2] + "є"
    elif last.endswith("ий"):
        last = last[:-2] + "е"
    words[-1] = last
    return " ".join(words)


def _last_word_to_genitive(phrase: str) -> str:
    """Масчинний називний -> родовий відмінок (потрібен для року у даті:
    "...дев'яносто перший" -> "...дев'яносто першого")."""
    words = phrase.rsplit(" ", 1)
    last = words[-1]
    if last.endswith("ій"):
        last = last[:-2] + "ього"
    elif last.endswith("ий"):
        last = last[:-2] + "ого"
    words[-1] = last
    return " ".join(words)


# Абревіатури / скорочення -> повне слово (озвучуються природно).
ABBREVIATIONS = {
    r"\bт\.?д\.?\b": "тому подібне",
    r"\bт\.?п\.?\b": "тому подібне",
    r"\bі\.?т\.?д\.?\b": "і так далі",
    # Обов'язкова крапка після "н" — без неї "не" збігається зі звичайним
    # словом "не" (заперечення), що ламало б звичайні речення.
    r"\bдо\s*н\.\s?е\.?\b": "до нашої ери",
    r"\bн\.\s?е\.?\b": "нашої ери",
    r"\bкв\.?м\.?\b": "квадратних метрів",
    r"\bгрн\.?\b": "гривень",
    r"\bкм/год\b": "кілометрів на годину",
    r"\bкм\.?\b": "кілометрів",
    r"\bм\.?\b(?=\s|$)": "метрів",
    r"\bкг\.?\b": "кілограмів",
    r"\bг\.?\b(?=\s|$)": "грамів",
    r"\bвул\.?\b": "вулиця",
    r"\bм\.\s": "місто ",
    r"\bоб\.?л\.?\b": "область",
    r"\bр\.?н\.?\b": "район",
    r"\bр\.\b(?=\s|$)": "року",
    r"\bрр\.\b": "років",
    r"\bст\.\b": "століття",
    r"\%": " відсотків",
    r"\bдол\.?\b": "доларів",
    r"\$": " доларів ",
    r"\b₴": " гривень ",
}

# Літерні абревіатури, які варто читати по буквах або словом-скороченням.
ACRONYMS = {
    "США": "Ес Ша А", "ООН": "О ОН", "НАТО": "НАТО", "ЄС": "Є Ес",
    "МВС": "Ем Ве Ес", "СБУ": "Ес Бе У", "ЗСУ": "Зе Се У",
    "ІТ": "Ай Ті", "ШІ": "Ша І", "АІ": "Ей Ай", "AI": "Ей Ай",
    "USB": "Ю-Ес-Бі", "PDF": "Пі-Ді-Еф", "API": "Ей-Пі-Ай",
    "URL": "Ю-Ар-Ел", "GPU": "Джі-Пі-Ю", "CPU": "Сі-Пі-Ю",
    "TTS": "Ті-Ті-Ес", "RVC": "Ар-Ві-Сі", "Wi-Fi": "Вай-Фай", "WiFi": "Вай-Фай",
}

_DATE_RE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{2,4})\b(?:\s*(?:року|р\.))?")
_TIME_RE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
_DECIMAL_RE = re.compile(r"\b\d+[.,]\d+\b")
_INT_RE = re.compile(r"(?<![\w.,])\d+(?![\w.,])")
_ORDINAL_SUFFIX_RE = re.compile(r"\b(\d+)-(й|м|му|го|ї|ю|х|те|ого|ому)\b", re.IGNORECASE)


def _num_uk(n: int) -> str:
    try:
        return num2words(n, lang="uk")
    except Exception:
        return str(n)


def _day_ordinal(day: int) -> str:
    """Число місяця у середньому роді ("число" — сер. рід): "двадцять четверте"."""
    try:
        word = num2words(day, lang="uk", to="ordinal")
        return _last_word_to_neuter(word)
    except Exception:
        return _num_uk(day)


def _year_ordinal_genitive(year: int) -> str:
    """Рік у родовому відмінку порядкового числівника (як природно кажуть
    українською після слова "року"): "тисяча дев'ятсот дев'яносто першого"."""
    try:
        word = num2words(year, lang="uk", to="ordinal")
    except Exception:
        return _num_uk(year)
    # "одна тисяча ..." по-українськи для року звучить природніше без "одна".
    word = re.sub(r"^одна тисяча\b", "тисяча", word)
    return _last_word_to_genitive(word)


def _replace_date(match: re.Match) -> str:
    day, month, year = int(match.group(1)), int(match.group(2)), match.group(3)
    year_i = int(year)
    if len(year) == 2:
        year_i += 2000 if year_i < 50 else 1900
    if not (1 <= month <= 12) or day == 0:
        return match.group(0)
    day_word = _day_ordinal(day)
    month_word = _MONTHS_GENITIVE.get(month, "")
    year_word = _year_ordinal_genitive(year_i)
    return f"{day_word} {month_word} {year_word} року"


def _replace_time(match: re.Match) -> str:
    hh, mm = int(match.group(1)), int(match.group(2))
    hh_word = _num_uk(hh)
    if mm == 0:
        return f"{hh_word} годин рівно"
    mm_word = _num_uk(mm)
    return f"{hh_word} годин {mm_word} хвилин"


def _replace_decimal(match: re.Match) -> str:
    raw = match.group(0).replace(",", ".")
    whole, frac = raw.split(".", 1)
    whole_word = _num_uk(int(whole)) if whole else "нуль"
    frac_word = " ".join(_num_uk(int(d)) for d in frac)
    return f"{whole_word} ціла {frac_word}"


def _replace_ordinal_suffix(match: re.Match) -> str:
    n = int(match.group(1))
    try:
        return num2words(n, lang="uk", to="ordinal")
    except Exception:
        return _num_uk(n)


def _replace_int(match: re.Match) -> str:
    return _num_uk(int(match.group(0)))


def expand_acronyms(text: str) -> str:
    for acronym, spoken in ACRONYMS.items():
        text = re.sub(rf"(?<![А-Яа-яІіЇїЄєҐґA-Za-z]){re.escape(acronym)}(?![А-Яа-яІіЇїЄєҐґA-Za-z])", spoken, text)
    return text


def expand_abbreviations(text: str) -> str:
    for pattern, repl in ABBREVIATIONS.items():
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
    return text


def expand_dates_and_time(text: str) -> str:
    text = _DATE_RE.sub(_replace_date, text)
    text = _TIME_RE.sub(_replace_time, text)
    return text


def expand_numbers(text: str) -> str:
    text = _ORDINAL_SUFFIX_RE.sub(_replace_ordinal_suffix, text)
    text = _DECIMAL_RE.sub(_replace_decimal, text)
    text = _INT_RE.sub(_replace_int, text)
    return text


def verbalize_text(text: str) -> str:
    """Повний конвеєр вербалізації для одного фрагмента тексту."""
    if not text.strip():
        return text
    result = text
    result = expand_acronyms(result)
    result = expand_abbreviations(result)
    result = expand_dates_and_time(result)
    result = expand_numbers(result)
    result = re.sub(r"\s+", " ", result).strip()
    return result
