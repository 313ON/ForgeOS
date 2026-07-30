from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
STATIC_ROOT = PROJECT_ROOT / "Backend" / "app" / "static"
INVOICE_UPLOAD_DIR = STATIC_ROOT / "uploads" / "invoices"
ALLOWED_INVOICE_EXTENSIONS = frozenset({".pdf", ".jpg", ".jpeg", ".png", ".webp"})
MAX_INVOICE_BYTES = 10 * 1024 * 1024


def invoice_extension(filename: str) -> str:
    """Return a validated lowercase invoice extension."""
    extension = Path(filename).suffix.casefold()
    if extension not in ALLOWED_INVOICE_EXTENSIONS:
        raise ValueError("Unsupported invoice type")
    return extension


def save_invoice(content: bytes, filename: str) -> str:
    """Persist invoice bytes under a UUID filename and return its static-relative path."""
    if len(content) > MAX_INVOICE_BYTES:
        raise ValueError("Invoice exceeds the 10 MB upload limit")
    extension = invoice_extension(filename)
    INVOICE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{extension}"
    destination = INVOICE_UPLOAD_DIR / stored_name
    destination.write_bytes(content)
    return Path("uploads", "invoices", stored_name).as_posix()


def resolve_invoice(relative_path: str) -> Path:
    """Resolve a stored invoice path while preventing traversal outside static storage."""
    candidate = (STATIC_ROOT / relative_path).resolve()
    static_root = STATIC_ROOT.resolve()
    if static_root not in candidate.parents or not candidate.is_file():
        raise FileNotFoundError("Invoice file not found")
    return candidate


def content_type_for(path: Path) -> str:
    """Return a safe MIME type for an invoice response."""
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"
