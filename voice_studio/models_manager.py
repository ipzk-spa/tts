"""Збереження RVC-моделей (.pth + .index) з дедуплікацією за SHA-256.

Якщо файл із таким самим вмістом уже лежить у models/uploads/rvc/ —
новий не копіюється, повертається існуючий шлях. Тимчасові `_upload_*`
у outputs/ прибираються одразу.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

from voice_studio.config import OUTPUT_DIR, RVC_UPLOADS_DIR

_HASH_INDEX = RVC_UPLOADS_DIR / ".hash_index.json"
_SAFE_NAME_RE = re.compile(r"[^\w.\-()+]+", re.UNICODE)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _load_index() -> dict:
    if not _HASH_INDEX.is_file():
        return {}
    try:
        data = json.loads(_HASH_INDEX.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_index(index: dict) -> None:
    RVC_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    _HASH_INDEX.write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _clean_original_name(name: str) -> str:
    base = Path(name).name
    while base.startswith("_upload_"):
        base = base[len("_upload_") :]
    base = _SAFE_NAME_RE.sub("_", base).strip("._")
    return base or "model.bin"


def _unique_dest(preferred: Path) -> Path:
    if not preferred.exists():
        return preferred
    stem, suffix = preferred.stem, preferred.suffix
    for i in range(2, 1000):
        candidate = preferred.with_name(f"{stem}_{i}{suffix}")
        if not candidate.exists():
            return candidate
    return preferred.with_name(f"{stem}_{hashlib.md5(stem.encode()).hexdigest()[:8]}{suffix}")


def _find_indexed(digest: str) -> Path | None:
    index = _load_index()
    entry = index.get(digest)
    if not entry:
        return None
    existing = Path(entry.get("path", ""))
    if existing.is_file():
        return existing
    return None


def _index_put(digest: str, path: Path) -> None:
    index = _load_index()
    index[digest] = {
        "path": str(path.resolve()),
        "name": path.name,
        "sha256": digest,
    }
    _save_index(index)


def _store_by_hash(src: Path, original_name: str) -> tuple[str, bool]:
    """Повертає (шлях, reused?). reused=True якщо файл уже був."""
    digest = _sha256_file(src)
    existing = _find_indexed(digest)
    if existing is not None:
        return str(existing.resolve()), True

    # Швидкий прохід лише по `_upload_*` (сміття старих версій), не по всіх ГБ.
    for candidate in RVC_UPLOADS_DIR.glob("_upload_*"):
        if not candidate.is_file() or candidate.suffix.lower() != src.suffix.lower():
            continue
        try:
            if _sha256_file(candidate) == digest:
                _index_put(digest, candidate)
                return str(candidate.resolve()), True
        except OSError:
            continue

    clean = _clean_original_name(original_name)
    dest = _unique_dest(RVC_UPLOADS_DIR / clean)
    # Якщо вже є файл із тим самим іменем і розміром — перевіримо хеш.
    if dest.exists() and dest.stat().st_size == src.stat().st_size:
        try:
            if _sha256_file(dest) == digest:
                _index_put(digest, dest)
                return str(dest.resolve()), True
        except OSError:
            pass
        dest = _unique_dest(RVC_UPLOADS_DIR / f"{dest.stem}_new{dest.suffix}")

    shutil.copy2(src, dest)
    _index_put(digest, dest)
    return str(dest.resolve()), False


def save_rvc_files(
    pth_file: str | None,
    index_file: str | None,
    pth_original_name: str | None = None,
    index_original_name: str | None = None,
) -> tuple[str, str, str]:
    """Зберігає RVC-файли. Повертає (pth_path, index_path, status_message)."""
    RVC_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    saved_pth = ""
    saved_index = ""
    notes: list[str] = []

    if pth_file:
        src = Path(pth_file)
        if src.is_file():
            name = pth_original_name or src.name
            path, reused = _store_by_hash(src, name)
            saved_pth = path
            label = Path(path).name
            notes.append(
                f"Модель: {label}" + (" (вже була, дублікат не створено)" if reused else "")
            )

    if index_file:
        src = Path(index_file)
        if src.is_file():
            name = index_original_name or src.name
            path, reused = _store_by_hash(src, name)
            saved_index = path
            label = Path(path).name
            notes.append(
                f"Індекс: {label}" + (" (вже був, дублікат не створено)" if reused else "")
            )

    message = "\n".join(notes) if notes else "Файли не вибрано."
    return saved_pth, saved_index, message


def cleanup_temp_uploads() -> int:
    """Прибирає тимчасові `_upload_*` з outputs/ і сміттєві `_upload_*` у rvc/,
    якщо той самий вміст уже збережено під нормальним ім'ям (через індекс)."""
    removed = 0
    if OUTPUT_DIR.is_dir():
        for path in OUTPUT_DIR.glob("_upload_*"):
            try:
                path.unlink(missing_ok=True)
                removed += 1
            except OSError:
                pass

    if not RVC_UPLOADS_DIR.is_dir():
        return removed

    index = _load_index()
    indexed_paths = {
        Path(v["path"]).resolve()
        for v in index.values()
        if isinstance(v, dict) and v.get("path")
    }

    for path in list(RVC_UPLOADS_DIR.glob("_upload_*")):
        if not path.is_file():
            continue
        try:
            digest = _sha256_file(path)
        except OSError:
            continue
        kept = _find_indexed(digest)
        if kept is not None and kept.resolve() != path.resolve():
            try:
                path.unlink(missing_ok=True)
                removed += 1
            except OSError:
                pass
            continue
        # Перейменувати сміттєве ім'я на чисте, якщо це єдиний екземпляр.
        if kept is None or kept.resolve() == path.resolve():
            clean = _clean_original_name(path.name)
            dest = RVC_UPLOADS_DIR / clean
            if dest.resolve() == path.resolve():
                _index_put(digest, path)
                continue
            if not dest.exists():
                try:
                    path.rename(dest)
                    _index_put(digest, dest)
                    removed += 0  # не видалено, а перейменовано
                except OSError:
                    _index_put(digest, path)
            else:
                # Чисте ім'я зайняте іншим файлом — лишаємо як є в індексі.
                _index_put(digest, path)

    # Прибрати з індексу мертві шляхи.
    alive = {}
    for digest, entry in _load_index().items():
        p = Path(entry.get("path", ""))
        if p.is_file():
            alive[digest] = entry
    _save_index(alive)
    return removed
