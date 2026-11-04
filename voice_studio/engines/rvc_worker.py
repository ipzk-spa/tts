"""Окремий процес для RVC-конверсії голосу (запускається у .venv-rvc).

Працює через JSON-файли, щоб уникнути проблем із кодуванням консолі Windows
для кириличного тексту.

Використання:
    python rvc_worker.py request.json

Режим "convert_audio" — гібрид: конвертує вже готовий WAV
(з Robinhad/StyleTTS2) вашою RVC-моделлю.
{
  "mode": "convert_audio",
  "model_path": "...\\model.pth",
  "index_path": "...\\model.index" | "",
  "input_wav": "...\\base_audio.wav",
  "f0_method": "rmvpe",
  "index_rate": 0.75,
  "pitch": 0,
  "output_wav": "...\\out.wav"
}

Результат пишеться у result.json поруч (той самий шлях + .result.json):
{"ok": true, "sample_rate": 40000, "output_wav": "..."}
або
{"ok": false, "error": "..."}

Примітка: пакет tts-with-rvc у vc_infer.rvc_convert має баг — якщо vc_single
падає всередині, повертає (traceback_str, (None, None)), а потім
scipy.io.wavfile.write на tuple дає незрозуміле "'tuple' object has no
attribute 'dtype'". Тут викликаємо VC напряму і поверхнево ловимо справжню
помилку.
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path


def _as_audio_array(opt_wav):
    """Нормалізує вихід vc_single до numpy-масиву (або кидає зрозумілу помилку)."""
    import numpy as np

    if opt_wav is None:
        raise RuntimeError("RVC повернув порожній аудіорезультат.")

    # Помилковий шлях vc_single: return info, (None, None)
    if isinstance(opt_wav, tuple):
        if all(x is None for x in opt_wav):
            raise RuntimeError(
                "RVC не зміг конвертувати аудіо (внутрішня помилка моделі/індексу/"
                "методу F0). Перевірте шляхи до .pth/.index і спробуйте інший F0-метод."
            )
        # деякі збірки повертають (audio, extra)
        for item in opt_wav:
            if hasattr(item, "dtype"):
                opt_wav = item
                break
        else:
            raise RuntimeError(f"RVC повернув неочікуваний результат: {type(opt_wav)}")

    if not hasattr(opt_wav, "dtype"):
        raise RuntimeError(f"RVC повернув не-масив: {type(opt_wav)}")

    arr = np.asarray(opt_wav)
    if arr.ndim > 1:
        arr = arr.mean(axis=-1) if arr.shape[-1] <= 2 else arr.mean(axis=0)
    if arr.dtype.kind == "f":
        arr = np.clip(arr, -1.0, 1.0)
    return arr


def _ensure_ffmpeg_on_path() -> str:
    """RVC load_audio вимагає CLI 'ffmpeg' у PATH. У проєкті вже є бінарник
    imageio-ffmpeg (основний .venv) — додаємо його каталог у PATH процесу."""
    candidates: list[Path] = []
    try:
        import imageio_ffmpeg

        candidates.append(Path(imageio_ffmpeg.get_ffmpeg_exe()))
    except Exception:
        pass

    root = Path(__file__).resolve().parents[2]
    candidates.extend([
        root / ".venv" / "Lib" / "site-packages" / "imageio_ffmpeg" / "binaries" / "ffmpeg-win-x86_64-v7.1.exe",
        root / ".venv" / "Lib" / "site-packages" / "imageio_ffmpeg" / "binaries" / "ffmpeg.exe",
    ])
    # будь-який ffmpeg*.exe у binaries
    bin_dir = root / ".venv" / "Lib" / "site-packages" / "imageio_ffmpeg" / "binaries"
    if bin_dir.is_dir():
        candidates.extend(sorted(bin_dir.glob("ffmpeg*.exe")))

    for exe in candidates:
        if exe and exe.is_file():
            folder = str(exe.parent)
            path_now = os.environ.get("PATH", "")
            if folder.lower() not in path_now.lower():
                os.environ["PATH"] = folder + os.pathsep + path_now
            # також зручне ім'я 'ffmpeg.exe' поруч, якщо бінарник з довгою назвою
            alias = exe.parent / "ffmpeg.exe"
            if exe.name.lower() != "ffmpeg.exe" and not alias.exists():
                try:
                    import shutil

                    shutil.copy2(exe, alias)
                except Exception:
                    pass
            return str(exe if exe.name.lower() == "ffmpeg.exe" or not alias.exists() else alias)

    raise RuntimeError(
        "Не знайдено ffmpeg для RVC. Встановіть imageio-ffmpeg у .venv "
        "(pip install imageio-ffmpeg) або додайте ffmpeg до PATH."
    )


def _patch_load_audio_without_ffmpeg() -> None:
    """Надійніше завантаження WAV через soundfile (наші вхідні файли завжди WAV),
    щоб не залежати від ffmpeg CLI, якщо PATH-патч не спрацював."""
    import numpy as np
    import soundfile as sf
    try:
        import tts_with_rvc.infer.lib.audio as audio_mod
    except Exception:
        return

    def load_audio(file, sr):  # noqa: ANN001
        file = audio_mod.clean_path(file)
        if not os.path.exists(file):
            raise RuntimeError(
                "You input a wrong audio path that does not exists, please fix it!"
            )
        data, file_sr = sf.read(file, dtype="float32", always_2d=False)
        if getattr(data, "ndim", 1) > 1:
            data = data.mean(axis=1)
        if int(file_sr) != int(sr):
            # простий лінійний ресемплінг без librosa (щоб менше залежностей)
            duration = len(data) / float(file_sr)
            n_out = int(round(duration * sr))
            if n_out <= 0:
                return np.zeros(0, dtype=np.float32)
            x_old = np.linspace(0.0, 1.0, num=len(data), endpoint=False)
            x_new = np.linspace(0.0, 1.0, num=n_out, endpoint=False)
            data = np.interp(x_new, x_old, data).astype(np.float32)
        return np.asarray(data, dtype=np.float32).flatten()

    audio_mod.load_audio = load_audio


def _convert_audio(
    model_path: str,
    input_wav: str,
    output_wav: str,
    index_path: str = "",
    f0_method: str = "rmvpe",
    index_rate: float = 0.75,
    pitch: int = 0,
    device: str | None = None,
) -> tuple[int, str]:
    """Прямий виклик RVC VC.vc_single з коректною обробкою помилок і записом WAV."""
    import numpy as np
    import soundfile as sf
    import torch
    from scipy.io import wavfile
    from tts_with_rvc.infer.vc.config import Config
    from tts_with_rvc.infer.vc.modules import VC
    from fairseq.data.dictionary import Dictionary

    # ffmpeg на PATH + soundfile-fallback для load_audio
    try:
        _ensure_ffmpeg_on_path()
    except RuntimeError:
        pass
    _patch_load_audio_without_ffmpeg()

    # безпечне завантаження pickle для newer torch
    try:
        torch.serialization.safe_globals([Dictionary])
        torch.serialization.add_safe_globals([Dictionary])
    except Exception:
        pass

    if not Path(model_path).is_file():
        raise FileNotFoundError(f"Модель RVC не знайдена: {model_path}")
    if not Path(input_wav).is_file():
        raise FileNotFoundError(f"Вхідний WAV не знайдено: {input_wav}")

    config = Config()
    if device:
        config.device = device
        if hasattr(config, "device"):
            config.device = device
    vc = VC(config)
    if device and hasattr(vc.config, "device"):
        vc.config.device = device

    vc.get_vc(model_path)

    file_index = index_path if index_path and Path(index_path).is_file() else ""
    file_index2 = ""

    tgt_sr, opt_wav = vc.vc_single(
        0,
        input_wav,
        int(pitch),
        None,
        f0_method or "rmvpe",
        file_index,
        file_index2,
        float(index_rate),
        3,       # filter_radius
        0,       # resample_sr
        0.5,     # rms_mix_rate
        0.33,    # protect
    )

    # vc_single при except повертає (traceback_str, (None, None))
    if isinstance(tgt_sr, str) or (isinstance(opt_wav, tuple) and all(x is None for x in opt_wav)):
        err = tgt_sr if isinstance(tgt_sr, str) else "невідома помилка всередині RVC"
        raise RuntimeError(f"RVC vc_single failed:\n{err}")

    audio = _as_audio_array(opt_wav)
    sr = int(tgt_sr)

    out = Path(output_wav)
    out.parent.mkdir(parents=True, exist_ok=True)

    if audio.dtype.kind == "f":
        sf.write(str(out), audio.astype(np.float32), sr, subtype="PCM_16")
    else:
        wavfile.write(str(out), sr, audio)

    return sr, str(out)


def main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({"ok": False, "error": "no request file"}))
        return 1

    request_path = Path(sys.argv[1])
    result_path = request_path.with_suffix(".result.json")
    req = json.loads(request_path.read_text(encoding="utf-8"))
    mode = req.get("mode", "convert_audio")

    try:
        import torch

        device = "cuda:0" if torch.cuda.is_available() else "cpu"

        if mode == "convert_audio":
            sr, out_path = _convert_audio(
                model_path=req["model_path"],
                input_wav=req["input_wav"],
                output_wav=req["output_wav"],
                index_path=req.get("index_path") or "",
                f0_method=req.get("f0_method", "rmvpe"),
                index_rate=float(req.get("index_rate", 0.75)),
                pitch=int(req.get("pitch", 0)),
                device=device,
            )
        else:
            # Залишок standalone TTS-шляху (Edge → RVC) — для сумісності, але
            # UI його більше не пропонує. Використовуємо tts_with_rvc з
            # обгорткою поверх тієї ж проблеми запису.
            from tts_with_rvc import TTS_RVC
            from tts_with_rvc import vc_infer as vc_infer_mod
            import numpy as np
            import soundfile as sf

            # Патч: не даємо rvc_convert впасти на tuple
            _orig_write = vc_infer_mod.wavfile.write

            def _safe_write(path, rate, data):
                if isinstance(data, tuple) or not hasattr(data, "dtype"):
                    raise RuntimeError(
                        "RVC повернув помилку замість аудіо (tuple). "
                        "Див. повідомлення вище / логи fairseq."
                    )
                return _orig_write(path, rate, data)

            vc_infer_mod.wavfile.write = _safe_write

            engine = TTS_RVC(
                model_path=req["model_path"],
                index_path=req.get("index_path") or "",
                voice=req.get("edge_voice", "uk-UA-PolinaNeural"),
                device=device,
                f0_method=req.get("f0_method", "rmvpe"),
            )
            out_path = engine(
                text=req["text"],
                pitch=int(req.get("pitch", 0)),
                index_rate=float(req.get("index_rate", 0.75)),
            )
            data, sr = sf.read(str(out_path))
            target = req["output_wav"]
            Path(target).parent.mkdir(parents=True, exist_ok=True)
            sf.write(target, data, sr)
            out_path = target

        result_path.write_text(
            json.dumps({"ok": True, "sample_rate": int(sr), "output_wav": str(out_path)}),
            encoding="utf-8",
        )
    except Exception as exc:  # noqa: BLE001
        result_path.write_text(
            json.dumps({"ok": False, "error": f"{exc}\n{traceback.format_exc()}"}),
            encoding="utf-8",
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
