from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path

REFERENCE_DIR = Path(__file__).resolve().parents[2] / "data" / "references"
MAX_REFERENCE_BYTES = 25 * 1024 * 1024
ALLOWED_EXTENSIONS = frozenset(
    {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".txt", ".md", ".csv", ".doc", ".docx", ".xls", ".xlsx"}
)
PREVIEW_EXTENSIONS = frozenset({".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".txt", ".md"})


def save_reference(content: bytes, filename: str) -> tuple[str, str, bool]:
    if not content:
        raise ValueError("Reference file is empty")
    if len(content) > MAX_REFERENCE_BYTES:
        raise ValueError("Reference exceeds the 25 MB upload limit")
    extension = Path(filename).suffix.casefold()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("Unsupported reference file type")
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{extension}"
    (REFERENCE_DIR / stored_name).write_bytes(content)
    media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return stored_name, media_type, extension in PREVIEW_EXTENSIONS


def resolve_reference(stored_name: str) -> Path:
    candidate = (REFERENCE_DIR / stored_name).resolve()
    root = REFERENCE_DIR.resolve()
    if candidate.parent != root or not candidate.is_file():
        raise FileNotFoundError("Reference file not found")
    return candidate
