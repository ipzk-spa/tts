"""Довготривалий процес для другого якісного двигуна — StyleTTS2 Ukrainian
(patriotyk/styletts2-ukrainian, checkpoint patriotyk/styletts2_ukrainian_multispeaker).
Запускається у .venv-styletts2 і тримає модель + усі 30 файлів стилів
"теплими" в пам'яті, так само як engines/robinhad_worker.py для Robinhad.

Текстова підготовка відтворює точний конвеєр із оригінального Gradio-демо
(app.py на HF Space): заміна ручного "+" на комбінований наголос ->
NFKC-нормалізація -> уніфікація тире -> обов'язкова кінцева пунктуація ->
автоматичний наголос (Stressifier, що не трогає вже наголошені склади) ->
IPA-транскрипція -> токенізація -> сама модель.

Протокол: по одному JSON-рядку на запит через stdin, одна відповідь —
один JSON-рядок через stdout з префіксом "@@JSON@@".

Запит:  {"text": "...", "voice": "Тетяна Гончарова", "speed": 1.0, "output_wav": "..."}
Відповідь: {"ok": true, "output_wav": "...", "sample_rate": 24000}
        або {"ok": false, "error": "..."}

Керуючі команди: {"cmd": "ping"} -> {"ok": true, "pong": true}
                 {"cmd": "stop"} -> завершує процес
"""
from __future__ import annotations

import json
import os
import re
import sys
import traceback
from pathlib import Path
from unicodedata import normalize

MARK = "@@JSON@@"
_DASH_RE = re.compile(r"[᠆‐‑‒–—―⁻₋−⸺⸻]")
_SPACED_DASH_RE = re.compile(r" - ")


def _emit(obj: dict) -> None:
    sys.stdout.write(MARK + json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _prepare_text(text: str, stress_symbol: str, stressify) -> str:
    t = text.replace("+", stress_symbol)
    t = normalize("NFKC", t)
    t = _DASH_RE.sub("-", t)
    if t and t[-1] not in ".?!:-":
        t += "."
    t = _SPACED_DASH_RE.sub(": ", t)
    return stressify(t)


def main() -> int:
    voices_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")

    try:
        import torch
        from ipa_uk import ipa
        from styletts2_inference.models import StyleTTS2
        from ukrainian_word_stress import Stressifier, StressSymbol
    except Exception as exc:  # noqa: BLE001
        _emit({"ready": False, "error": f"{exc}\n{traceback.format_exc()}"})
        return 1

    stressify = Stressifier()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cuda":
        try:
            torch.backends.cudnn.benchmark = True
        except Exception:
            pass

    try:
        model = StyleTTS2(hf_path="patriotyk/styletts2_ukrainian_multispeaker", device=device)
    except Exception as exc:  # noqa: BLE001
        _emit({"ready": False, "error": f"{exc}\n{traceback.format_exc()}"})
        return 1

    styles: dict[str, "torch.Tensor"] = {}
    try:
        for pt_path in sorted(voices_dir.glob("*.pt")):
            name = pt_path.stem
            styles[name] = torch.load(str(pt_path), map_location=device, weights_only=False)
    except Exception as exc:  # noqa: BLE001
        _emit({"ready": False, "error": f"Не вдалося завантажити стилі голосу: {exc}"})
        return 1

    if not styles:
        _emit({
            "ready": False,
            "error": "У models/styletts2/voices немає жодного файлу стилю (.pt). "
                     "Запустіть tools\\setup_styletts2.ps1.",
        })
        return 1

    _emit({"ready": True, "sample_rate": 24000, "device": device, "voices": sorted(styles.keys())})

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue

        if req.get("cmd") == "ping":
            _emit({"ok": True, "pong": True})
            continue
        if req.get("cmd") == "stop":
            break

        try:
            text = req["text"]
            voice = req.get("voice") or next(iter(styles))
            speed = float(req.get("speed", 1.0))
            output_wav = req["output_wav"]

            if voice not in styles:
                raise ValueError(f"Невідомий голос StyleTTS2: {voice}")

            prepared = _prepare_text(text, StressSymbol.CombiningAcuteAccent, stressify)
            phonemes = ipa(prepared)
            if not phonemes:
                raise ValueError("Після обробки тексту не залишилось звуків для синтезу.")

            tokens = model.tokenizer.encode(phonemes)
            with torch.no_grad():
                wav = model(tokens, speed=speed, s_prev=styles[voice])

            import soundfile as sf

            wav_np = wav.detach().cpu().numpy() if hasattr(wav, "detach") else wav
            sf.write(str(output_wav), wav_np, 24000, "PCM_16", format="wav")

            _emit({
                "ok": True,
                "output_wav": output_wav,
                "sample_rate": 24000,
                "accented_text": prepared,
            })
        except Exception as exc:  # noqa: BLE001
            _emit({"ok": False, "error": f"{exc}\n{traceback.format_exc()}"})

    return 0


if __name__ == "__main__":
    sys.exit(main())
