import hashlib
import io
import re
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, UnidentifiedImageError

from .config import get_settings


class UploadError(ValueError):
    pass


def safe_filename(filename: str | None) -> str:
    name = (filename or "document").replace("\\", "/").split("/")[-1]
    name = re.sub(r"[^\w. -]", "_", name, flags=re.UNICODE).strip(" .")
    return name[:180] or "document"


def detect_type(content: bytes) -> tuple[str, str]:
    if content.startswith(b"%PDF-"):
        try:
            doc = pdfium.PdfDocument(content)
            if len(doc) == 0:
                raise UploadError("PDF has no pages")
            if len(doc) > 100:
                raise UploadError("PDF exceeds the 100-page limit")
            doc.close()
        except UploadError:
            raise
        except pdfium.PdfiumError as exc:
            if exc.err_code in {4, 5}:
                raise UploadError(
                    "Encrypted PDFs are not supported; upload an unlocked copy"
                ) from exc
            raise UploadError("PDF is damaged or unreadable") from exc
        except Exception as exc:
            raise UploadError("PDF is damaged or unreadable") from exc
        return "application/pdf", ".pdf"
    if content.startswith(b"\x89PNG\r\n\x1a\n") or content.startswith(b"\xff\xd8\xff"):
        try:
            with Image.open(io.BytesIO(content)) as image:
                image.verify()
            with Image.open(io.BytesIO(content)) as image:
                if image.width * image.height > 100_000_000:
                    raise UploadError("Image dimensions are too large")
                if image.format == "PNG":
                    return "image/png", ".png"
                if image.format == "JPEG":
                    return "image/jpeg", ".jpg"
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise UploadError("Image is damaged or unreadable") from exc
    raise UploadError("Unsupported file; upload a PDF, PNG, or JPEG")


def validate_upload(content: bytes) -> tuple[str, str]:
    if not content:
        raise UploadError("File is empty")
    if len(content) > get_settings().max_upload_mb * 1024 * 1024:
        raise UploadError(f"File exceeds the {get_settings().max_upload_mb} MB limit")
    return detect_type(content)


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def storage_path(workspace_id: str, key: str) -> Path:
    root = get_settings().storage_root.resolve()
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", workspace_id) or not re.fullmatch(
        r"[a-zA-Z0-9_.-]+", key
    ):
        raise ValueError("Invalid storage identifier")
    path = (root / workspace_id / key).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Storage path escapes root")
    return path


def save_source(workspace_id: str, content: bytes, extension: str) -> str:
    key = digest(content) + extension
    path = storage_path(workspace_id, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(content)
    return key


def save_export(workspace_id: str, key: str, content: bytes) -> None:
    path = storage_path(workspace_id, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(content)
