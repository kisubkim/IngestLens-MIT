"""Format detection and conversion to PDF so every document is rendered page by page the same way."""

import shutil
import subprocess
from pathlib import Path

import filetype

from ..config import settings
from . import pdfgen

OFFICE_EXT = {"doc", "docx", "ppt", "pptx", "xls", "xlsx", "odt", "odp", "ods", "rtf", "hwp"}
IMAGE_EXT = {"png", "jpg", "jpeg", "tif", "tiff", "bmp"}


def detect(path: Path) -> dict:
    ext = path.suffix.lower().lstrip(".")
    kind = filetype.guess(str(path))
    magic_mime = kind.mime if kind else None
    magic_ext = kind.extension if kind else None

    if magic_ext == "pdf" or (magic_ext is None and ext == "pdf"):
        fmt = "pdf"
    elif ext in IMAGE_EXT or (magic_mime or "").startswith("image/"):
        fmt = "image"
    elif ext in OFFICE_EXT:
        # docx/pptx/xlsx are ZIP containers, so magic bytes say "zip"; the extension picks the kind.
        fmt = ext
    else:
        fmt = "unknown"
    return {"extension": ext, "magic_mime": magic_mime, "magic_ext": magic_ext, "format": fmt,
            "mismatch": bool(magic_ext and magic_ext not in (ext, "zip") and not (magic_ext == "jpg" and ext == "jpeg"))}


def soffice_bin() -> str | None:
    return settings.soffice_path or shutil.which("soffice") or shutil.which("libreoffice")


def office_to_pdf(src: Path, out_dir: Path, timeout_s: int = 600) -> Path:
    exe = soffice_bin()
    if not exe:
        raise RuntimeError("LibreOffice(soffice) not found. Install it or set RAG_SOFFICE_PATH.")
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [exe, "--headless", "--convert-to", "pdf", "--outdir", str(out_dir), str(src)],
        check=True, capture_output=True, timeout=timeout_s,
    )
    pdf = out_dir / (src.stem + ".pdf")
    if not pdf.exists():
        raise RuntimeError(f"LibreOffice produced no PDF for {src.name}")
    return pdf


def image_to_pdf(src: Path, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    return pdfgen.image_to_pdf(src, out_dir / (src.stem + ".pdf"))
