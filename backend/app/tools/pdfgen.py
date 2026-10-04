"""Writing PDFs with ReportLab: image wrapping, the native Office renderer, and synthetic test/eval documents.

Coordinates are PDF points with a top-left origin, like everywhere else in the app (ReportLab itself is
bottom-left). Korean needs a CJK font: RAG_CJK_FONT, else the first TrueType font found on the system,
else ReportLab's built-in CID font, which is not embedded (text extraction works, but rendering the
page needs a Korean font on the machine that renders it).
"""

import io
from pathlib import Path

from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from ..config import settings

A4 = (595.28, 841.89)
FONT_CANDIDATES = [
    "C:/Windows/Fonts/malgun.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/nanum/NanumGothic.ttf",
    "/usr/share/fonts/naver-nanum/NanumGothic.ttf",
    "/usr/share/fonts/truetype/unfonts-core/UnDotum.ttf",
    "/usr/share/fonts/truetype/baekmuk/gulim.ttf",
    "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
    "/Library/Fonts/AppleGothic.ttf",
]
CID_FALLBACK = "HYGothic-Medium"
_font: dict | None = None


def cjk_font() -> dict:
    """Registers the CJK font once per process. Returns {name, source, embedded, rule_id, tried}."""
    global _font
    if _font is not None:
        return _font
    tried = []
    configured = settings.cjk_font.strip()
    for path in ([configured] if configured else []) + FONT_CANDIDATES:
        if not Path(path).is_file():
            continue
        try:
            # TrueType outlines only: ReportLab cannot embed CFF-based .otf fonts (e.g. Noto Sans CJK).
            pdfmetrics.registerFont(TTFont("cjk", path))
        except Exception as e:  # unsupported font file: try the next one
            tried.append({"path": path, "error": f"{type(e).__name__}: {e}"})
            continue
        _font = {"name": "cjk", "source": path, "embedded": True,
                 "rule_id": "font_configured" if path == configured else "font_system", "tried": tried}
        return _font
    pdfmetrics.registerFont(UnicodeCIDFont(CID_FALLBACK))
    _font = {"name": CID_FALLBACK, "source": f"ReportLab CID {CID_FALLBACK}", "embedded": False,
             "rule_id": "font_cid_fallback", "tried": tried}
    return _font


def _wrap(text: str, font: str, size: float, width: float) -> list[str]:
    """Greedy word wrap; words wider than the box are broken by character."""
    lines: list[str] = []
    for para in text.split("\n"):
        cur = ""
        for word in para.split(" "):
            cand = f"{cur} {word}" if cur else word
            if pdfmetrics.stringWidth(cand, font, size) <= width:
                cur = cand
                continue
            if cur:
                lines.append(cur)
            cur = ""
            for ch in word:
                if pdfmetrics.stringWidth(cur + ch, font, size) > width and cur:
                    lines.append(cur)
                    cur = ""
                cur += ch
        lines.append(cur)
    return lines


class PdfWriter:
    """Minimal page builder with top-left coordinates (pages default to A4)."""

    def __init__(self, path: Path | str):
        self.font = cjk_font()["name"]
        self.c = canvas.Canvas(str(path), pageCompression=1)
        self.size, self.h = None, None

    def new_page(self, width: float = A4[0], height: float = A4[1]) -> "PdfWriter":
        if self.h is not None:
            self.c.showPage()
        self.c.setPageSize((width, height))
        self.size, self.h = (width, height), height
        return self

    def text(self, x: float, y: float, s: str, size: float = 11) -> None:
        """y is the baseline, measured from the top."""
        self.c.setFont(self.font, size)
        self.c.drawString(x, self.h - y, s)

    def textbox(self, rect, s: str, size: float = 11, leading: float = 1.25) -> int:
        """Wraps s into rect (x0, y0, x1, y1). Returns the number of lines that did not fit (drawn nothing then)."""
        x0, y0, x1, y1 = rect
        lines = _wrap(s, self.font, size, x1 - x0)
        fit = int((y1 - y0 - size) // (size * leading)) + 1
        if len(lines) > fit:
            return len(lines) - fit
        self.c.setFont(self.font, size)
        for i, line in enumerate(lines):
            self.c.drawString(x0, self.h - (y0 + size + i * size * leading), line)
        return 0

    def line(self, p0, p1, width: float = 1) -> None:
        self.c.setLineWidth(width)
        self.c.line(p0[0], self.h - p0[1], p1[0], self.h - p1[1])

    def rect(self, r, width: float = 1, fill: tuple[float, float, float] | None = None) -> None:
        """Black outline; fill is an RGB triple in 0..1."""
        self.c.setLineWidth(width)
        if fill is not None:
            self.c.setFillColorRGB(*fill)
        self.c.rect(r[0], self.h - r[3], r[2] - r[0], r[3] - r[1], stroke=1, fill=int(fill is not None))
        self.c.setFillColorRGB(0, 0, 0)

    def polyline(self, points, width: float = 1) -> None:
        self.c.setLineWidth(width)
        path = self.c.beginPath()
        path.moveTo(points[0][0], self.h - points[0][1])
        for x, y in points[1:]:
            path.lineTo(x, self.h - y)
        self.c.drawPath(path, stroke=1, fill=0)

    def image(self, r, img) -> None:
        """img: a PIL image, encoded bytes, or a file path (a JPEG path is embedded without re-encoding)."""
        src = ImageReader(io.BytesIO(img) if isinstance(img, bytes) else str(img) if isinstance(img, Path) else img)
        self.c.drawImage(src, r[0], self.h - r[3], r[2] - r[0], r[3] - r[1])

    def save(self) -> None:
        if self.h is None:
            self.new_page()
        self.c.save()


def image_to_pdf(src: Path, out: Path, default_dpi: float = 96) -> Path:
    """One page per image frame (multi-page TIFF), sized from the image's DPI (96 when missing)."""
    from PIL import Image, ImageSequence

    w = PdfWriter(out)
    with Image.open(src) as im:
        single_jpeg = im.format == "JPEG"
        for frame in ImageSequence.Iterator(im):
            dpi = frame.info.get("dpi") or (default_dpi, default_dpi)
            dx, dy = (float(v) if v and float(v) > 1 else default_dpi for v in dpi[:2])
            pw, ph = frame.width * 72 / dx, frame.height * 72 / dy
            w.new_page(pw, ph)
            if single_jpeg:
                w.image((0, 0, pw, ph), src)
            else:
                f = frame.convert("RGBA" if "A" in frame.getbands() else "RGB")
                w.image((0, 0, pw, ph), f)
    w.save()
    return out
