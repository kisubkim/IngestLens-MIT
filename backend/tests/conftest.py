import os
import tempfile
from pathlib import Path

import pytest
from PIL import Image

# Settings are read at import time, so point the app at a throwaway data dir first.
os.environ["RAG_DATA_DIR"] = tempfile.mkdtemp(prefix="rag-test-")
os.environ["RAG_SETTINGS_FILE"] = str(Path(tempfile.mkdtemp(prefix="rag-settings-")) / "settings.local.yaml")

from app.tools.pdf import open_pdf  # noqa: E402
from app.tools.pdfgen import PdfWriter  # noqa: E402

BODY = (
    "Retrieval augmented generation combines a retriever with a generator. "
    "문서를 청크로 나누고 임베딩한 뒤 벡터 DB에 저장한다. "
) * 6


def gray_image(w: int, h: int) -> Image.Image:
    return Image.new("RGB", (w, h), (200, 210, 220))


def write_pdf(path: Path, *pages) -> Path:
    """Each page is a function drawing on a fresh A4 page of a PdfWriter."""
    w = PdfWriter(path)
    for draw in pages:
        w.new_page()
        draw(w)
    w.save()
    return path


def one_page(path: Path, draw):
    """(doc, page) for a one-page PDF; close the doc when done."""
    doc = open_pdf(write_pdf(path, draw))
    return doc, doc.page(0)


def _text_page(title: str):
    def draw(w: PdfWriter) -> None:
        w.text(72, 80, title, size=20)
        assert w.textbox((72, 110, 520, 700), BODY, size=10) == 0
    return draw


def _table_page(w: PdfWriter) -> None:
    w.text(72, 60, "Quarterly results", size=20)
    x0, y0, cw, rh, rows, cols = 72, 100, 110, 40, 12, 4
    for r in range(rows + 1):
        w.line((x0, y0 + r * rh), (x0 + cols * cw, y0 + r * rh))
    for c in range(cols + 1):
        w.line((x0 + c * cw, y0), (x0 + c * cw, y0 + rows * rh))
    for r in range(rows):
        for c in range(cols):
            w.text(x0 + c * cw + 6, y0 + r * rh + 24, f"r{r}c{c}", size=9)


def _diagram_page(w: PdfWriter) -> None:
    for i in range(160):
        x, y = 60 + (i % 16) * 30, 100 + (i // 16) * 50
        w.rect((x, y, x + 20, y + 20))
    w.text(72, 700, "Block diagram", size=10)


def _scanned_page(w: PdfWriter) -> None:
    w.image((0, 0, *w.size), Image.new("RGB", (300, 400), (230, 230, 230)))


FIGURE_RECT = (72, 380, 420, 600)


def _figure_page(w: PdfWriter) -> None:
    """Text page with an embedded figure and a caption right below it."""
    w.text(72, 80, "3. Architecture", size=20)
    assert w.textbox((72, 110, 520, 370), BODY, size=10) == 0
    w.image(FIGURE_RECT, gray_image(348, 220))
    w.text(72, 620, "그림 1. 시스템 구성도", size=9)


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    """Pages: 0 text, 1 text, 2 table, 3 diagram, 4 scanned, 5 text with figure + caption."""
    return write_pdf(tmp_path / "sample.pdf", _text_page("1. Introduction"), _text_page("2. Method"),
                     _table_page, _diagram_page, _scanned_page, _figure_page)
