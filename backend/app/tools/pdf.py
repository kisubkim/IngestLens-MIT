"""PDF reading: page features for profiling, rule classification, native extraction and rendering.

pdfplumber / pdfminer.six parse a page (text boxes and lines with font sizes, images, vector paths,
ruled tables); pypdfium2 renders it. Every bbox is in PDF points with a top-left origin, relative to
the crop box and after /Rotate: the same space as the rendered page image.
"""

import io
import threading
from collections import Counter

import pdfplumber
import pypdfium2 as pdfium
from pdfminer.layout import LTChar, LTContainer, LTCurve, LTImage, LTTextBox, LTTextLine

# boxes_flow=None: no reading-order analysis (we sort blocks ourselves); all_texts: also text inside form XObjects.
LAPARAMS = {"all_texts": True, "boxes_flow": None}
_pdfium_lock = threading.Lock()  # PDFium is not thread-safe; renders in one process run one at a time


def _area(r) -> float:
    return max(0.0, (r[2] - r[0])) * max(0.0, (r[3] - r[1]))


def _clip(bbox, page_rect) -> list[float]:
    x0, y0, x1, y1 = bbox
    return [max(x0, page_rect[0]), max(y0, page_rect[1]), min(x1, page_rect[2]), min(y1, page_rect[3])]


class Table:
    """A ruled table found on the page: bbox and cell rows (None for an empty cell)."""

    def __init__(self, bbox: list[float], rows: list[list]):
        self.bbox, self.rows = bbox, rows

    def extract(self) -> list[list]:
        return self.rows

    def to_markdown(self) -> str:
        def cell(c) -> str:
            return ("" if c is None else str(c)).strip().replace("\n", "<br>").replace("|", "\\|")

        width = max(len(r) for r in self.rows)
        lines = ["|" + "|".join(cell(c) for c in list(r) + [None] * (width - len(r))) + "|" for r in self.rows]
        lines.insert(1, "|" + "---|" * width)
        return "\n".join(lines) + "\n\n"


class Page:
    """One parsed page. Use as a context manager (or call close()) to release pdfminer's layout cache."""

    def __init__(self, doc: "PdfDoc", index: int, pp):
        self.doc, self.index, self._pp = doc, index, pp
        cx0, ctop, cx1, cbottom = pp.cropbox
        self.rect = [0.0, 0.0, float(cx1 - cx0), float(cbottom - ctop)]
        # pdfminer coordinates (bottom-left, mediabox based) -> top-left, crop box based (as pdfplumber does, plus the crop offset).
        self._dx = float(pp.mediabox[0] - cx0)
        self._dy = float(pp.mediabox[1] - ctop)
        self._h = float(pp.height)
        self.blocks: list[dict] = []
        self.images: list[list[float]] = []
        self.drawings: list[list[float]] = []
        self._tables: list[Table] | None = None
        self._walk(pp.layout)

    def _box(self, o) -> list[float]:
        return [o.x0 + self._dx, self._h - o.y1 + self._dy, o.x1 + self._dx, self._h - o.y0 + self._dy]

    def _walk(self, container) -> None:
        for o in container:
            if isinstance(o, LTTextBox):
                self._block(o, list(o))
            elif isinstance(o, LTTextLine):
                self._block(o, [o])
            elif isinstance(o, LTImage):
                self.images.append(self._box(o))
            elif isinstance(o, LTCurve):  # LTLine and LTRect are curves too
                self.drawings.append(self._box(o))
            elif isinstance(o, LTContainer):  # LTFigure (form XObject)
                self._walk(o)

    def _block(self, box, lines) -> None:
        out = []
        for line in lines:
            text = line.get_text().strip()
            sizes = [c.size for c in line if isinstance(c, LTChar) and c.get_text().strip()]
            if text and sizes:
                out.append({"bbox": self._box(line), "text": text, "size": min(sizes), "sizes": sizes})
        if out:
            self.blocks.append({"bbox": self._box(box), "lines": out})

    def tables(self) -> list[Table]:
        """Ruled tables (pdfplumber "lines" strategy). Single cells and single rows/columns are boxes, not tables."""
        if self._tables is None:
            self._tables = []
            for t in self._pp.find_tables():
                rows = t.extract()
                if len(rows) < 2 or max(len(r) for r in rows) < 2:
                    continue
                x0, top, x1, bottom = t.bbox
                cx0, ctop = self._pp.cropbox[:2]
                self._tables.append(Table([x0 - cx0, top - ctop, x1 - cx0, bottom - ctop], rows))
        return self._tables

    def text(self) -> str:
        return "\n".join(line["text"] for b in sorted(self.blocks, key=_reading_key) for line in b["lines"])

    def render(self, dpi: int, clip: list[float] | None = None, fmt: str = "png") -> bytes:
        return self.doc.render(self.index, dpi, clip, fmt)

    def close(self) -> None:
        self._pp.close()

    def __enter__(self) -> "Page":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def _reading_key(block: dict) -> tuple:
    return (round(block["bbox"][1]), block["bbox"][0])


class PdfDoc:
    """Opens the file lazily: PDFium for page count and rendering, pdfplumber for page content."""

    def __init__(self, path):
        self.path = str(path)
        self._pdfium = None
        self._plumber = None

    def _pdf(self):
        if self._pdfium is None:
            try:
                self._pdfium = pdfium.PdfDocument(self.path)
            except pdfium.PdfiumError as e:
                if "password" in str(e).lower():
                    raise ValueError("PDF is password protected") from e
                raise
        return self._pdfium

    @property
    def page_count(self) -> int:
        with _pdfium_lock:
            return len(self._pdf())

    def page(self, index: int) -> Page:
        if self._plumber is None:
            self._plumber = pdfplumber.open(self.path, laparams=LAPARAMS)
        return Page(self, index, self._plumber.pages[index])

    def pages(self):
        for i in range(self.page_count):
            with self.page(i) as p:
                yield p

    def render(self, index: int, dpi: int, clip: list[float] | None = None, fmt: str = "png") -> bytes:
        with _pdfium_lock:
            page = self._pdf()[index]
            try:
                w, h = page.get_size()
                crop = (0, 0, 0, 0)
                if clip is not None:
                    x0, y0, x1, y1 = max(clip[0], 0), max(clip[1], 0), min(clip[2], w), min(clip[3], h)
                    crop = (x0, h - y1, w - x1, y0)  # PDFium crops from (left, bottom, right, top)
                img = page.render(scale=dpi / 72, crop=crop).to_pil()
            finally:
                page.close()
        buf = io.BytesIO()
        if fmt == "jpeg":
            img.convert("RGB").save(buf, "JPEG", quality=85)
        else:
            img.save(buf, "PNG")
        return buf.getvalue()

    def close(self) -> None:
        if self._plumber is not None:
            self._plumber.close()
        if self._pdfium is not None:
            with _pdfium_lock:
                self._pdfium.close()

    def __enter__(self) -> "PdfDoc":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def open_pdf(path) -> PdfDoc:
    return PdfDoc(path)


def page_features(page: Page) -> dict:
    rect = page.rect
    page_area = _area(rect) or 1.0

    drawings = len(page.drawings)

    # Table detection is the slowest probe; tables need ruling lines, so skip pages without drawings.
    tables, table_area, table_boxes = 0, 0.0, []
    if drawings:
        found = page.tables()
        tables = len(found)
        table_boxes = [t.bbox for t in found]
        table_area = sum(_area(_clip(b, rect)) for b in table_boxes)

    text_chars = 0
    table_chars = 0
    text_area = 0.0
    size_hist: Counter = Counter()
    for block in page.blocks:
        text_area += _area(_clip(block["bbox"], rect))
        for line in block["lines"]:
            n = len(line["text"])
            text_chars += n
            for s in line["sizes"]:
                size_hist[str(round(s, 1))] += 1
            if any(inside(line["bbox"], b) for b in table_boxes):
                table_chars += n

    image_area = sum(_area(_clip(b, rect)) for b in page.images)

    return {
        "text_chars": text_chars,
        "text_area_ratio": round(min(text_area / page_area, 1.0), 3),
        "images": len(page.images),
        "image_area_ratio": round(min(image_area / page_area, 1.0), 3),
        "drawings": drawings,
        "tables": tables,
        "table_area_ratio": round(min(table_area / page_area, 1.0), 3),
        # Share of the page's text inside tables: a small table with little text around it still dominates the page.
        "table_text_share": round(table_chars / text_chars, 3) if text_chars else 0.0,
        "size_hist": dict(size_hist),
    }


# Condition key -> (feature name, comparison). "min_" means feature >= value, "max_" means <=.
def _check(features: dict, key: str, value: float) -> tuple[bool, float]:
    kind, name = key.split("_", 1)
    actual = features[name]
    ok = actual >= value if kind == "min" else actual <= value
    # Margin relative to the threshold, used for confidence: 0 at the threshold, 1 when far past it.
    denom = abs(value) or 1.0
    margin = (actual - value) / denom if kind == "min" else (value - actual) / denom
    return ok, margin


def classify(features: dict, profiler_rules: dict) -> dict:
    """First matching rule wins. Returns label, rule id, confidence and per-condition evidence."""
    evidence = []
    for rule in profiler_rules["rules"]:
        checks = {k: _check(features, k, v) for k, v in rule["when"].items()}
        evidence.append({"rule": rule["id"], "matched": all(ok for ok, _ in checks.values())})
        if all(ok for ok, _ in checks.values()):
            weakest = min(m for _, m in checks.values())
            confidence = round(0.5 + 0.5 * min(weakest, 1.0), 2)
            return {
                "label": rule["label"],
                "rule_id": rule["id"],
                "confidence": confidence,
                "conditions": {k: {"threshold": rule["when"][k], "actual": features[k.split("_", 1)[1]]} for k in checks},
                "evaluated": evidence,
            }
    default = profiler_rules["default"]
    return {"label": default["label"], "rule_id": default["id"], "confidence": 0.4, "conditions": {}, "evaluated": evidence}


def body_font_size(size_hist: dict) -> float | None:
    """Most common character size."""
    if not size_hist:
        return None
    return float(max(size_hist.items(), key=lambda kv: kv[1])[0])


def extract_text_elements(page: Page, heading_min_size: float | None) -> list[dict]:
    """Text blocks in reading order, split where lines switch between heading and body size
    (layout analysis often glues a heading to the paragraph next to it). Heading-size runs up to 200 chars are titles."""
    out = []
    for block in sorted(page.blocks, key=_reading_key):
        groups: list[list] = []  # [is_heading, lines, bbox]
        for line in block["lines"]:
            head = heading_min_size is not None and line["size"] >= heading_min_size
            lb = line["bbox"]
            if groups and groups[-1][0] == head:
                g = groups[-1]
                g[1].append(line["text"])
                g[2] = [min(g[2][0], lb[0]), min(g[2][1], lb[1]), max(g[2][2], lb[2]), max(g[2][3], lb[3])]
            else:
                groups.append([head, [line["text"]], list(lb)])
        for head, lines, bbox in groups:
            text = "\n".join(lines)
            out.append({"type": "title" if head and len(text) <= 200 else "text", "bbox": [round(v, 1) for v in bbox], "content": text})
    return out


def inside(inner, outer, tol: float = 2.0) -> bool:
    return inner[0] >= outer[0] - tol and inner[1] >= outer[1] - tol and inner[2] <= outer[2] + tol and inner[3] <= outer[3] + tol
