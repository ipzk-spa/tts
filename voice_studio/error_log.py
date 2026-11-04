"""Запис помилок, попереджень і всього консольного виводу у logs/errors.txt.

Файл зручно скинути для діагностики. Ротація: > 5 МБ → errors.old.txt.
"""
from __future__ import annotations

import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path

from voice_studio.config import LOGS_DIR

ERROR_LOG_FILE = LOGS_DIR / "errors.txt"
_OLD_LOG_FILE = LOGS_DIR / "errors.old.txt"
_MAX_LOG_BYTES = 5 * 1024 * 1024
_SEPARATOR = "-" * 72
_lock = threading.Lock()
_tee_installed = False


def _log_path() -> Path:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    return ERROR_LOG_FILE


def _maybe_rotate(path: Path) -> None:
    if not path.is_file() or path.stat().st_size <= _MAX_LOG_BYTES:
        return
    try:
        if _OLD_LOG_FILE.exists():
            _OLD_LOG_FILE.unlink(missing_ok=True)
        path.replace(_OLD_LOG_FILE)
    except OSError:
        pass


def _append(block: str) -> None:
    path = _log_path()
    with _lock:
        _maybe_rotate(path)
        try:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(block)
                if not block.endswith("\n"):
                    fh.write("\n")
        except OSError:
            pass


def log_console(message: str, source: str = "console") -> None:
    """Дублює рядок консолі в errors.txt (без traceback)."""
    text = (message or "").rstrip()
    if not text:
        return
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _append(f"[{stamp}] {source.upper()} | {text}\n")


def log_error(
    context: str,
    exc: BaseException | None = None,
    details: str = "",
) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        _SEPARATOR,
        f"[{stamp}] ERROR | {context}",
    ]
    if details:
        lines.append(details.rstrip())
    if exc is not None:
        lines.append(f"{type(exc).__name__}: {exc}")
        lines.append(
            "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)).rstrip()
        )
    lines.append("")
    _append("\n".join(lines))


def log_warning(context: str, message: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _append(
        "\n".join(
            [
                _SEPARATOR,
                f"[{stamp}] WARNING | {context}",
                message.rstrip(),
                "",
            ]
        )
    )


class _TeeStream:
    """Дублює write()/flush() у файл логу."""

    def __init__(self, original, source: str) -> None:
        self._original = original
        self._source = source
        self._buf = ""

    def write(self, data: str) -> int:
        if not isinstance(data, str):
            data = str(data)
        try:
            written = self._original.write(data)
        except Exception:
            written = len(data)
        self._buf += data
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line.strip():
                log_console(line, source=self._source)
        return written

    def flush(self) -> None:
        if self._buf.strip():
            log_console(self._buf, source=self._source)
            self._buf = ""
        try:
            self._original.flush()
        except Exception:
            pass

    def isatty(self) -> bool:
        try:
            return bool(self._original.isatty())
        except Exception:
            return False

    def __getattr__(self, name: str):
        return getattr(self._original, name)


def install_stdio_tee() -> None:
    """Усі print()/stderr → також у logs/errors.txt."""
    global _tee_installed
    if _tee_installed:
        return
    sys.stdout = _TeeStream(sys.stdout, "stdout")  # type: ignore[assignment]
    sys.stderr = _TeeStream(sys.stderr, "stderr")  # type: ignore[assignment]
    _tee_installed = True


def install_excepthook() -> None:
    previous = sys.excepthook

    def _hook(exc_type, exc, tb) -> None:  # noqa: ANN001
        if issubclass(exc_type, SystemExit):
            previous(exc_type, exc, tb)
            return
        try:
            log_error(
                "uncaught",
                exc if isinstance(exc, BaseException) else None,
                details="".join(traceback.format_exception(exc_type, exc, tb)),
            )
        except Exception:
            pass
        previous(exc_type, exc, tb)

    sys.excepthook = _hook
