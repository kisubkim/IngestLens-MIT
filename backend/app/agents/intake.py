"""Intake agent: detect the real format and normalize everything to PDF."""

import asyncio
from pathlib import Path

from ..config import rules_cfg, settings
from ..db import session
from ..events import emit_event, record_decision
from ..models import Document
from ..tools.office import OFFICE_EXT, detect, image_to_pdf, office_to_pdf, soffice_bin
from ..tools.office_native import extract_hints, render_native
from ..tools.pdf import open_pdf
from ..tools.pdfgen import cjk_font
from .common import PipelineState, get_document, update_summary

NATIVE_FORMATS = {"docx", "pptx", "xlsx"}

STEP = "intake"


async def intake(state: PipelineState) -> dict:
    run_id = state["run_id"]
    doc = get_document(state["doc_id"])
    src = settings.resolve(doc.path)
    info = detect(src)
    fmt = info["format"]
    out_dir = settings.data_dir / "converted" / doc.id
    inputs = {**info, "size_mb": round(doc.size / 2**20, 2)}

    if info["mismatch"]:
        emit_event(run_id, "warning", STEP, f"Extension .{info['extension']} does not match content ({info['magic_mime']})", info)

    hints: dict = {}
    alternatives: list = []
    if fmt == "pdf":
        pdf, rule, choice = src, "magic_pdf", "PDF: parse natively"
    elif fmt == "image":
        pdf = await asyncio.to_thread(image_to_pdf, src, out_dir)
        rule, choice = "image_wrap", "Image: wrap as a one-page PDF"
    elif fmt in OFFICE_EXT:
        pdf, rule, choice, hints, alternatives = await _office(run_id, src, fmt, out_dir, inputs)
    else:
        raise ValueError(f"Unsupported format: .{info['extension']} ({info['magic_mime']})")

    with open_pdf(pdf) as d:
        page_count = d.page_count  # raises ValueError for a password-protected PDF
    inputs["page_count"] = page_count

    record_decision(
        run_id, STEP, "document format", choice,
        rule_id=rule, inputs=inputs, alternatives=alternatives, confidence=1.0 if not info["mismatch"] else 0.7,
        reasoning="Every format is rendered as PDF pages so profiling, parsing and bbox overlays work the same way.",
    )
    if hints:
        update_summary(run_id, "office", _hint_summary(hints))

    with session() as s:
        d = s.get(Document, doc.id)
        d.format, d.pdf_path, d.page_count = fmt, settings.stored_path(pdf), page_count

    return {"pdf_path": str(pdf), "format": fmt, "page_count": page_count, "hints": hints}


async def _office(run_id: str, src: Path, fmt: str, out_dir: Path, inputs: dict):
    """LibreOffice when available (best layout fidelity); native rendering otherwise, and always for xlsx
    by default. Both paths also read structure hints from the original file."""
    cfg = rules_cfg()["office"]
    soffice = soffice_bin()
    native_ok = fmt in NATIVE_FORMATS
    use_native = native_ok and (cfg["prefer"] == "native" or not soffice or (fmt == "xlsx" and cfg["xlsx"] == "native"))
    inputs |= {"libreoffice": soffice or None, "native_renderer": native_ok, "prefer": cfg["prefer"]}

    if use_native:
        emit_event(run_id, "progress", STEP, f"Rendering .{fmt} natively")
        pdf, hints = await asyncio.to_thread(render_native, src, out_dir, fmt, cfg["xlsx_rows_per_page"], cfg["xlsx_max_rows"])
        hints["renderer"] = "native"
        _record_font(run_id, hints["font"])
        why = ("spreadsheets keep every table readable" if fmt == "xlsx" and soffice
               else "configured preference" if soffice else "LibreOffice is not installed")
        alternatives = [{"choice": "LibreOffice", "reason_rejected": why}]
        return pdf, "office_native", f"{fmt.upper()}: render natively ({why})", hints, alternatives
    if not soffice:
        raise ValueError(f".{fmt} needs LibreOffice (only docx/pptx/xlsx have a native renderer). Install it or set RAG_SOFFICE_PATH.")
    emit_event(run_id, "progress", STEP, f"Converting .{fmt} to PDF with LibreOffice")
    pdf = await asyncio.to_thread(office_to_pdf, src, out_dir)
    hints = await asyncio.to_thread(extract_hints, src, fmt) if native_ok else {}
    if hints:
        hints["renderer"] = "libreoffice"
    alternatives = [{"choice": "native renderer", "reason_rejected": "LibreOffice keeps the original layout"}] if native_ok else []
    return pdf, "office_convert", f"{fmt.upper()}: convert to PDF with LibreOffice", hints, alternatives


def _record_font(run_id: str, font: dict) -> None:
    tried = cjk_font()["tried"]
    if font["embedded"]:
        record_decision(run_id, STEP, "office font", f"embed {Path(font['source']).name}", rule_id=font["rule_id"],
                        inputs={"font": font["source"], "RAG_CJK_FONT": settings.cjk_font or None, "rejected_files": tried},
                        confidence=1.0, reasoning="Hangul text needs a TrueType CJK font embedded in the rendered PDF.")
        return
    record_decision(run_id, STEP, "office font", "non-embedded CID font", rule_id=font["rule_id"],
                    inputs={"font": font["source"], "RAG_CJK_FONT": settings.cjk_font or None, "rejected_files": tried},
                    alternatives=[{"choice": "embedded TrueType font", "reason_rejected": "no usable font found; set RAG_CJK_FONT or install NanumGothic"}],
                    confidence=0.5,
                    reasoning="Text extraction still works, but page images show Hangul only where a Korean font is installed.")
    emit_event(run_id, "warning", STEP, "No Korean TrueType font found: rendered pages use a non-embedded CID font")


def _hint_summary(h: dict) -> dict:
    out = {"kind": h.get("kind"), "renderer": h.get("renderer")}
    if h.get("kind") == "pptx":
        out |= {"slides": len(h["slides"]), "with_notes": sum(bool(s["notes"]) for s in h["slides"]),
                "charts": sum(len(s["charts"]) for s in h["slides"])}
    elif h.get("kind") == "docx":
        out |= {"headings": len(h["headings"]), "images": h.get("images", 0)}
    elif h.get("kind") == "xlsx":
        out |= {"sheets": h["sheets"]}
    return out
