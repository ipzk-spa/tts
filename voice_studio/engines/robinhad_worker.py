"""Довготривалий процес для robinhad/ukrainian-tts (Tacotron2 + HiFiGAN).

Тримає модель теплою в .venv-robinhad. За замовчуванням використовує
наголос моделі (stress_with_model) — як офіційний HF-демо; словниковий
наголос лишається опцією. decode_conf передається лише коли клієнт явно
задає нестандартні значення (інакше — дефолти synthesizer, природніший тон).

Протокол: JSON-рядок у stdin → відповідь @@JSON@@ + JSON у stdout.
"""
from __future__ import annotations

import json
import os
import sys
import traceback

MARK = "@@JSON@@"


def _emit(obj: dict) -> None:
    sys.stdout.write(MARK + json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main() -> int:
    cache_folder = sys.argv[1] if len(sys.argv) > 1 else "."

    try:
        os.chdir(cache_folder)
    except Exception as exc:  # noqa: BLE001
        _emit({"ready": False, "error": f"Не вдалося перейти в {cache_folder}: {exc}"})
        return 1

    try:
        import torch
        from torch import no_grad
        from ukrainian_tts.formatter import preprocess_text
        from ukrainian_tts.stress import sentence_to_stress, stress_dict, stress_with_model
        from ukrainian_tts.tts import TTS
        import soundfile as sf
    except Exception as exc:  # noqa: BLE001
        _emit({"ready": False, "error": f"{exc}\n{traceback.format_exc()}"})
        return 1

    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cuda":
        try:
            torch.backends.cudnn.benchmark = True
        except Exception:
            pass

    try:
        tts = TTS(cache_folder=".", device=device)
    except Exception as exc:  # noqa: BLE001
        _emit({"ready": False, "error": f"{exc}\n{traceback.format_exc()}"})
        return 1

    _emit({
        "ready": True,
        "sample_rate": int(tts.synthesizer.fs),
        "device": device,
    })

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue

        if req.get("cmd") == "ping":
            _emit({"ok": True, "pong": True, "device": device})
            continue
        if req.get("cmd") == "stop":
            break

        try:
            text = req["text"]
            voice = req.get("voice", "tetiana")
            output_wav = req["output_wav"]
            stress_mode = str(req.get("stress_mode", "model")).lower()
            stress_fn = stress_with_model if stress_mode == "model" else stress_dict

            processed = preprocess_text(text)
            processed = sentence_to_stress(processed, stress_fn)

            # decode_conf лише якщо клієнт явно просить кастомну стабільність —
            # інакше офіційні дефолти (природніше, менше «робота»).
            use_custom = bool(req.get("use_custom_decode", False))
            synth_kwargs = {"spembs": tts.xvectors[voice][0]}
            if use_custom:
                synth_kwargs["decode_conf"] = {
                    "threshold": float(req.get("threshold", 0.5)),
                    "maxlenratio": float(req.get("maxlenratio", 10.0)),
                    "minlenratio": 0.0,
                    "use_att_constraint": bool(req.get("use_att_constraint", False)),
                }

            ctx = torch.inference_mode if hasattr(torch, "inference_mode") else no_grad
            with ctx():
                wav = tts.synthesizer(processed, **synth_kwargs)["wav"]

            sf.write(
                str(output_wav),
                wav.view(-1).cpu().numpy(),
                int(tts.synthesizer.fs),
                "PCM_16",
                format="wav",
            )

            _emit({
                "ok": True,
                "output_wav": output_wav,
                "sample_rate": int(tts.synthesizer.fs),
                "accented_text": processed,
                "device": device,
                "stress_mode": stress_mode,
            })
        except Exception as exc:  # noqa: BLE001
            _emit({"ok": False, "error": f"{exc}\n{traceback.format_exc()}"})

    return 0


if __name__ == "__main__":
    sys.exit(main())
