import os
import tempfile
from pathlib import Path

import pymupdf
import pytest

# Settings are read at import time, so point the app at a throwaway data dir first.
os.environ["RAG_DATA_DIR"] = tempfile.mkdtemp(prefix="rag-test-")
os.environ["RAG_SETTINGS_FILE"] = str(Path(tempfile.mkdtemp(prefix="rag-settings-")) / "settings.local.yaml")

BODY = (
    "Retrieval augmented generation combines a retriever with a generator. "
    "문서를 청크로 나누고 임베딩한 뒤 벡터 DB에 저장한다. "
) * 6


def _text_page(doc: pymupdf.Document, title: str) -> None:
    page = doc.new_page()
    page.insert_text((72, 80), title, fontsize=20)
    page.insert_textbox(pymupdf.Rect(72, 110, 520, 700), BODY, fontsize=10, fontname="korea")


def _table_page(doc: pymupdf.Document) -> None:
    page = doc.new_page()
    page.insert_text((72, 60), "Quarterly results", fontsize=20)
    x0, y0, cw, rh, rows, cols = 72, 100, 110, 40, 12, 4
    for r in range(rows + 1):
        page.draw_line((x0, y0 + r * rh), (x0 + cols * cw, y0 + r * rh))
    for c in range(cols + 1):
        page.draw_line((x0 + c * cw, y0), (x0 + c * cw, y0 + rows * rh))
    for r in range(rows):
        for c in range(cols):
            page.insert_text((x0 + c * cw + 6, y0 + r * rh + 24), f"r{r}c{c}", fontsize=9)


def _diagram_page(doc: pymupdf.Document) -> None:
    page = doc.new_page()
    for i in range(160):
        x, y = 60 + (i % 16) * 30, 100 + (i // 16) * 50
        page.draw_rect(pymupdf.Rect(x, y, x + 20, y + 20))
    page.insert_text((72, 700), "Block diagram", fontsize=10)


def _scanned_page(doc: pymupdf.Document) -> None:
    page = doc.new_page()
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 300, 400), 0)
    pix.set_rect(pix.irect, (230, 230, 230))
    page.insert_image(page.rect, pixmap=pix)


def gray_pixmap(w: int, h: int) -> pymupdf.Pixmap:
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, w, h), 0)
    pix.set_rect(pix.irect, (200, 210, 220))
    return pix


FIGURE_RECT = pymupdf.Rect(72, 380, 420, 600)


def _figure_page(doc: pymupdf.Document) -> None:
    """Text page with an embedded figure and a caption right below it."""
    page = doc.new_page()
    page.insert_text((72, 80), "3. Architecture", fontsize=20)
    page.insert_textbox(pymupdf.Rect(72, 110, 520, 370), BODY, fontsize=10, fontname="korea")
    page.insert_image(FIGURE_RECT, pixmap=gray_pixmap(348, 220))
    page.insert_text((72, 620), "그림 1. 시스템 구성도", fontsize=9, fontname="korea")


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    """Pages: 0 text, 1 text, 2 table, 3 diagram, 4 scanned, 5 text with figure + caption."""
    doc = pymupdf.open()
    _text_page(doc, "1. Introduction")
    _text_page(doc, "2. Method")
    _table_page(doc)
    _diagram_page(doc)
    _scanned_page(doc)
    _figure_page(doc)
    path = tmp_path / "sample.pdf"
    doc.save(path)
    doc.close()
    return path
