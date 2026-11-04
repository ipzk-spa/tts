"""Spag Voice Studio (SVS+) — HTTP API + статичний веб-інтерфейс."""
from __future__ import annotations

import atexit
import json
import os
import queue
import socket
import sys
import tempfile
import threading
import time
import webbrowser
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice_studio import pipeline
from voice_studio.audio.export import save_mp3_file, save_wav_file
from voice_studio.config import (
    APP_LOGO,
    APP_SHORT,
    APP_TITLE,
    ETA_SEC_PER_CHUNK_CPU,
    ETA_SEC_PER_CHUNK_GPU,
    OUTPUT_DIR,
    SERVER_HOST,
    SERVER_PORT,
)
from voice_studio.engines import robinhad_engine, rvc_engine, styletts2_engine
from voice_studio.error_log import (
    ERROR_LOG_FILE,
    install_excepthook,
    install_stdio_tee,
    log_console,
    log_error,
)
from voice_studio.models_manager import cleanup_temp_uploads, save_rvc_files

install_excepthook()
install_stdio_tee()

WEB_DIR = Path(__file__).resolve().parent / "web"

app = FastAPI(title=APP_TITLE, docs_url=None, redoc_url=None)

if (WEB_DIR / "css").is_dir():
    app.mount("/css", StaticFiles(directory=WEB_DIR / "css"), name="css")
if (WEB_DIR / "js").is_dir():
    app.mount("/js", StaticFiles(directory=WEB_DIR / "js"), name="js")


class VerbalizeRequest(BaseModel):
    text: str = ""


class VerbalizeResponse(BaseModel):
    text: str


class StressRequest(BaseModel):
    text: str = ""
    mode: str = Field(default="auto", pattern="^(auto|manual|none)$")


class StressResponse(BaseModel):
    text: str


class SynthesizeRequest(BaseModel):
    engine: str = Field(..., pattern="^(robinhad|styletts2)$")
    text: str = ""
    robinhad_voice: str = "tetiana"
    robinhad_verbalize: bool = True
    robinhad_threshold: float = 0.5
    robinhad_maxlenratio: float = 10.0
    robinhad_att_constraint: bool = False
    robinhad_stress_mode: str = Field(default="model", pattern="^(model|dictionary)$")
    styletts2_voice: str = ""
    styletts2_speed: float = 1.0
    styletts2_verbalize: bool = True
    hybrid_enabled: bool = False
    hybrid_pth: str = ""
    hybrid_index: str = ""
    hybrid_f0: str = "rmvpe"
    hybrid_index_rate: float = 0.75
    hybrid_pitch: int = 0


class SynthesizeResponse(BaseModel):
    ok: bool
    status: str = ""
    preview: str = ""
    wav_url: str | None = None
    mp3_url: str | None = None
    wav_filename: str | None = None
    mp3_filename: str | None = None


class UploadRvcResponse(BaseModel):
    message: str
    pth_path: str = ""
    index_path: str = ""


def _port_is_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def _resolve_port(host: str, preferred: int, max_tries: int = 20) -> int:
    for port in range(preferred, preferred + max_tries):
        if _port_is_free(host, port):
            return port
    return preferred


def _safe_output_path(filename: str) -> Path:
    safe = Path(filename).name
    if safe != filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Недопустиме ім'я файлу.")
    path = (OUTPUT_DIR / safe).resolve()
    if path.parent != OUTPUT_DIR.resolve():
        raise HTTPException(status_code=403, detail="Доступ заборонено.")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Файл не знайдено.")
    return path


def _save_outputs(sr: int, audio, prefix: str) -> tuple[str, str | None]:
    ts = time.strftime("%Y%m%d-%H%M%S")
    wav_name = f"{prefix}_{ts}.wav"
    mp3_name = f"{prefix}_{ts}.mp3"
    wav_path = str(OUTPUT_DIR / wav_name)
    mp3_path = str(OUTPUT_DIR / mp3_name)
    save_wav_file(wav_path, sr, audio)
    mp3_result = save_mp3_file(mp3_path, sr, audio)
    return wav_name, Path(mp3_result).name if mp3_result else None


def _gpu_hint() -> bool:
    """Груба евристика: якщо встановлений хоч один GPU-рушій — очікуємо CUDA."""
    return robinhad_engine.is_installed() or styletts2_engine.is_installed()


def _eta_table() -> dict:
    return ETA_SEC_PER_CHUNK_GPU if _gpu_hint() else ETA_SEC_PER_CHUNK_CPU


def _shutdown_engines() -> None:
    try:
        removed = cleanup_temp_uploads()
        if removed:
            log_console(f"Очищено тимчасових RVC-файлів: {removed}", "cleanup")
    except Exception as exc:
        log_error("cleanup_temp_uploads", exc)
    robinhad_engine.shutdown()
    styletts2_engine.shutdown()


atexit.register(_shutdown_engines)


@app.on_event("startup")
def _on_startup() -> None:
    try:
        removed = cleanup_temp_uploads()
        log_console(
            f"{APP_TITLE} старт. Прибрано дублікатів/темпів: {removed}. Лог: {ERROR_LOG_FILE}",
            "startup",
        )
    except Exception as exc:
        log_error("startup_cleanup", exc)


@app.get("/")
async def index() -> FileResponse:
    index_path = WEB_DIR / "index.html"
    if not index_path.is_file():
        raise HTTPException(status_code=500, detail="index.html не знайдено.")
    return FileResponse(index_path, media_type="text/html; charset=utf-8")


@app.get("/api/status")
async def api_status() -> dict:
    rh_voices = [{"label": lbl, "value": val} for lbl, val in robinhad_engine.VOICES]
    st_voices = styletts2_engine.list_voices()
    default_engine = "robinhad" if robinhad_engine.is_installed() else (
        "styletts2" if styletts2_engine.is_installed() else "robinhad"
    )
    return {
        "title": APP_TITLE,
        "short": APP_SHORT,
        "logo": APP_LOGO,
        "default_engine": default_engine,
        "eta_sec_per_chunk": _eta_table(),
        "gpu_likely": _gpu_hint(),
        "robinhad": {
            "installed": robinhad_engine.is_installed(),
            "status": robinhad_engine.status_message(),
            "voices": rh_voices,
            "device": robinhad_engine.device_name(),
        },
        "styletts2": {
            "installed": styletts2_engine.is_installed(),
            "status": styletts2_engine.status_message(),
            "voices": st_voices,
        },
        "rvc": {
            "available": rvc_engine.is_available(),
            "status": rvc_engine.status_message(),
            "f0_methods": rvc_engine.F0_METHODS,
        },
    }


@app.post("/api/verbalize", response_model=VerbalizeResponse)
async def api_verbalize(req: VerbalizeRequest) -> VerbalizeResponse:
    try:
        return VerbalizeResponse(text=pipeline.preview_verbalize(req.text))
    except Exception as exc:
        log_error("api/verbalize", exc, details=f"text_len={len(req.text)}")
        return VerbalizeResponse(text=req.text)


@app.post("/api/stress", response_model=StressResponse)
async def api_stress(req: StressRequest) -> StressResponse:
    try:
        return StressResponse(text=pipeline.preview_stress(req.text, mode=req.mode))
    except Exception as exc:
        log_error("api/stress", exc, details=f"text_len={len(req.text)}")
        return StressResponse(text=req.text)


def _run_synthesize(req: SynthesizeRequest, on_progress=None) -> SynthesizeResponse:
    if req.engine == "robinhad":
        sr, audio, preview = pipeline.synthesize_robinhad(
            req.text,
            req.robinhad_voice,
            do_verbalize=req.robinhad_verbalize,
            threshold=req.robinhad_threshold,
            maxlenratio=req.robinhad_maxlenratio,
            use_att_constraint=req.robinhad_att_constraint,
            stress_mode=req.robinhad_stress_mode,
            on_progress=on_progress,
        )
        prefix = "robinhad"
    else:
        voice = req.styletts2_voice or (styletts2_engine.list_voices() or [""])[0]
        sr, audio, preview = pipeline.synthesize_styletts2(
            req.text,
            voice,
            speed=req.styletts2_speed,
            do_verbalize=req.styletts2_verbalize,
            on_progress=on_progress,
        )
        prefix = "styletts2"

    status = "✅ Готово."
    if req.hybrid_enabled:
        sr, audio = pipeline.revoice_with_rvc(
            sr,
            audio,
            model_path=req.hybrid_pth,
            index_path=req.hybrid_index,
            f0_method=req.hybrid_f0,
            index_rate=req.hybrid_index_rate,
            pitch=req.hybrid_pitch,
            on_progress=on_progress,
        )
        prefix += "_hybridrvc"
        status = "✅ Готово (переозвучено вашою RVC-моделлю)."

    if on_progress:
        on_progress({
            "type": "progress",
            "phase": "export",
            "current": 1,
            "total": 1,
            "message": "Збереження WAV/MP3…",
        })

    wav_name, mp3_name = _save_outputs(sr, audio, prefix)
    return SynthesizeResponse(
        ok=True,
        status=status,
        preview=preview,
        wav_url=f"/api/download/{wav_name}",
        mp3_url=f"/api/download/{mp3_name}" if mp3_name else None,
        wav_filename=wav_name,
        mp3_filename=mp3_name,
    )


@app.post("/api/synthesize", response_model=SynthesizeResponse)
async def api_synthesize(req: SynthesizeRequest) -> SynthesizeResponse:
    try:
        return _run_synthesize(req)
    except Exception as exc:
        log_error(
            "api/synthesize",
            exc,
            details=(
                f"engine={req.engine} hybrid={req.hybrid_enabled} "
                f"text_len={len(req.text)}"
            ),
        )
        return SynthesizeResponse(ok=False, status=f"❌ {exc}")


@app.post("/api/synthesize/stream")
async def api_synthesize_stream(req: SynthesizeRequest) -> StreamingResponse:
    """NDJSON-потік: progress… → done|error. Для прогрес-бару в UI."""

    def event_stream():
        q: queue.Queue = queue.Queue()

        def on_progress(payload: dict) -> None:
            q.put(payload)

        def worker() -> None:
            try:
                result = _run_synthesize(req, on_progress=on_progress)
                q.put({"type": "done", **result.model_dump()})
            except Exception as exc:
                log_error(
                    "api/synthesize/stream",
                    exc,
                    details=f"engine={req.engine} text_len={len(req.text)}",
                )
                q.put({"type": "error", "ok": False, "status": f"❌ {exc}"})

        threading.Thread(target=worker, daemon=True).start()
        while True:
            item = q.get()
            yield json.dumps(item, ensure_ascii=False) + "\n"
            if item.get("type") in ("done", "error"):
                break

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


@app.get("/api/download/{filename}")
async def api_download(filename: str) -> FileResponse:
    path = _safe_output_path(filename)
    media = "audio/wav" if path.suffix.lower() == ".wav" else "audio/mpeg"
    return FileResponse(
        path,
        media_type=media,
        filename=path.name,
        headers={"Content-Disposition": f'attachment; filename="{path.name}"'},
    )


@app.post("/api/upload/rvc", response_model=UploadRvcResponse)
async def api_upload_rvc(
    pth: UploadFile | None = File(None),
    index: UploadFile | None = File(None),
) -> UploadRvcResponse:
    pth_tmp = index_tmp = None
    try:
        with tempfile.TemporaryDirectory(prefix="sss_rvc_") as tmp:
            tmp_dir = Path(tmp)
            pth_name = index_name = None
            if pth and pth.filename:
                pth_name = Path(pth.filename).name
                pth_tmp = tmp_dir / pth_name
                pth_tmp.write_bytes(await pth.read())
            if index and index.filename:
                index_name = Path(index.filename).name
                index_tmp = tmp_dir / index_name
                index_tmp.write_bytes(await index.read())

            saved_pth, saved_index, message = save_rvc_files(
                str(pth_tmp) if pth_tmp else None,
                str(index_tmp) if index_tmp else None,
                pth_original_name=pth_name,
                index_original_name=index_name,
            )

        cleanup_temp_uploads()
        return UploadRvcResponse(
            message=message,
            pth_path=saved_pth or "",
            index_path=saved_index or "",
        )
    except Exception as exc:
        log_error("api/upload/rvc", exc)
        return UploadRvcResponse(message=f"❌ {exc}")


def main() -> None:
    import uvicorn

    # UTF-8 для Windows-консолі (і/ї/є).
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

    port = _resolve_port(SERVER_HOST, SERVER_PORT)
    if port != SERVER_PORT:
        print(f"[{APP_SHORT}] Порт {SERVER_PORT} зайнятий — використовую порт {port}.")
    url = f"http://{SERVER_HOST}:{port}/"

    def _open_browser() -> None:
        if os.environ.get("VOICE_STUDIO_NO_BROWSER") == "1":
            return
        try:
            webbrowser.open(url)
        except Exception as exc:
            log_error("open_browser", exc)

    threading.Timer(1.2, _open_browser).start()

    print(f"[{APP_SHORT}] {APP_TITLE}")
    print(f"[{APP_SHORT}] Відкрийте у браузері: {url}")
    print(f"[{APP_SHORT}] Лог (консоль + помилки): {ERROR_LOG_FILE}")

    try:
        uvicorn.run(app, host=SERVER_HOST, port=port, log_level="warning")
    except OSError as exc:
        log_error("server_start", exc, details=f"host={SERVER_HOST} port={port}")
        print(f"[{APP_SHORT}] Не вдалося запустити сервер ({exc}).")
        print(f"[{APP_SHORT}] Деталі: {ERROR_LOG_FILE}")
        sys.exit(1)
    finally:
        _shutdown_engines()


if __name__ == "__main__":
    main()
