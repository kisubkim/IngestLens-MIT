"""Build the VLM evaluation set in evals/vlm/: one PDF whose image pages carry real content, plus expectations.

    python scripts/make_vlm_set.py

Pages: 1 text (control, no VLM), 2 scanned text, 3 scanned table, 4 text + bar chart image + caption,
5 text + flow diagram image + caption. The expectations in cases.json are the ground truth used by
scripts/eval_vlm.py. Add real scanned pages and figures in the same format to evaluate on data that matters.
"""

import io
import json
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evals" / "vlm"
sys.path.insert(0, str(ROOT / "backend"))

from app.tools.pdf import open_pdf  # noqa: E402
from app.tools.pdfgen import PdfWriter  # noqa: E402

TEXT_PAGE = ("1. 장비 개요", "본 장비는 반도체 식각 공정용 플라즈마 챔버이다. 챔버 내부 압력은 20 mTorr로 유지하며 "
             "RF 전력은 최대 1500W까지 인가할 수 있다. 정기 점검은 매월 첫째 주 화요일에 실시한다.")
SCAN_TITLE = "2. 비상 대응 절차"
SCAN_BODY = [
    "가스 누출 경보가 울리면 즉시 비상 정지 버튼을 누르고 작업장을 벗어난다.",
    "누출 가스가 NF3인 경우 환기 장치를 최대로 가동하고 안전팀(내선 4119)에 연락한다.",
    "복구 작업은 가스 농도가 1 ppm 이하로 떨어진 뒤에만 시작한다.",
    "모든 조치 내용은 사고 보고서 양식 SF-07에 기록하고 24시간 안에 제출한다.",
]
TABLE_TITLE = "3. 분기별 가동률"
TABLE_ROWS = [["구분", "가동률", "비가동 사유"], ["1분기", "92.1%", "정기 점검"], ["2분기", "88.4%", "펌프 교체"],
              ["3분기", "95.0%", "없음"], ["4분기", "90.7%", "전원 공사"]]
CHART = ("월별 웨이퍼 불량 수", [("1월", 120), ("2월", 180), ("3월", 90), ("4월", 210)])
FLOW = ["원료 투입", "혼합", "건조", "포장"]


def _box(w: PdfWriter, rect, text: str, size: float) -> None:
    assert w.textbox(rect, text, size=size) == 0, f"text does not fit: {text[:30]}"


def _line(w: PdfWriter, xy: tuple[float, float], text: str, size: float) -> None:
    """One line whose baseline is at xy[1]."""
    w.text(xy[0], xy[1], text, size=size)


def _render(draw, size: tuple[float, float], dpi: int) -> bytes:
    """Draw one page into a scratch PDF and rasterize it (PNG)."""
    with tempfile.TemporaryDirectory() as tmp:
        w = PdfWriter(Path(tmp) / "scratch.pdf")
        w.new_page(*size)
        draw(w)
        w.save()
        with open_pdf(Path(tmp) / "scratch.pdf") as d:
            return d.render(0, dpi)


def _scan(w: PdfWriter, draw, dpi: int = 130) -> None:
    """Rasterize a page and put only the image on a new page, like a scanner would."""
    png = _render(draw, (595.28, 841.89), dpi)
    w.new_page()
    w.image((0, 0, *w.size), png)


def _figure_page(w: PdfWriter, title: str, body: str, png: bytes, caption: str) -> None:
    w.new_page()
    _line(w, (72, 80), title, 20)
    _box(w, (72, 110, 520, 300), body, 11)
    iw, ih = Image.open(io.BytesIO(png)).size
    bottom = 320 + 420 * ih / iw  # keep the aspect ratio so the caption sits right under the image
    w.image((72, 320, 492, bottom), png)
    _line(w, (72, bottom + 20), caption, 9)


def _scan_text(s: PdfWriter) -> None:
    _line(s, (72, 80), SCAN_TITLE, 20)
    _box(s, (72, 110, 520, 700), "\n".join(SCAN_BODY), 12)


def _scan_table(s: PdfWriter) -> None:
    _line(s, (72, 70), TABLE_TITLE, 18)
    x0, y0, cw, rh = 72, 100, 150, 30
    for r in range(len(TABLE_ROWS) + 1):
        s.line((x0, y0 + r * rh), (x0 + 3 * cw, y0 + r * rh))
    for c in range(4):
        s.line((x0 + c * cw, y0), (x0 + c * cw, y0 + len(TABLE_ROWS) * rh))
    for r, row in enumerate(TABLE_ROWS):
        for c, v in enumerate(row):
            _line(s, (x0 + c * cw + 6, y0 + r * rh + 20), v, 11)


def _chart(c: PdfWriter) -> None:
    c.line((40, 220), (400, 220))
    c.line((40, 20), (40, 220))
    for i, (m, v) in enumerate(CHART[1]):
        x = 70 + i * 85
        c.rect((x, 220 - v * 0.9, x + 45, 220), fill=(0.2, 0.4, 0.8))
        _line(c, (x + 10, 238), m, 11)
        _line(c, (x + 10, 208 - v * 0.9), str(v), 10)
    _line(c, (150, 15), CHART[0], 12)


def _flow(d: PdfWriter) -> None:
    for i, name in enumerate(FLOW):
        x = 15 + i * 115
        d.rect((x, 70, x + 85, 120), width=1.5, fill=(0.9, 0.95, 1))
        _line(d, (x + 12, 100), name, 12)
        if i < len(FLOW) - 1:
            d.line((x + 85, 95), (x + 115, 95), width=1.5)
            d.polyline([(x + 108, 90), (x + 115, 95), (x + 108, 100)], width=1.5)
    d.rect((245, 150, 330, 190), width=1.5, fill=(1, 0.93, 0.9))
    _line(d, (262, 175), "수분 검사", 12)
    d.line((287, 120), (287, 150), width=1.5)
    _line(d, (150, 30), "제조 공정 흐름도", 13)


def make_pdf(path: Path) -> None:
    w = PdfWriter(path)
    w.new_page()
    _line(w, (72, 80), TEXT_PAGE[0], 20)
    _box(w, (72, 110, 520, 700), TEXT_PAGE[1], 11)

    _scan(w, _scan_text)
    _scan(w, _scan_table)

    _figure_page(w, "4. 품질 현황", "아래 그림은 월별 불량 웨이퍼 수를 나타낸다. 원인 분석은 품질팀이 담당한다.",
                 _render(_chart, (420, 260), 150), "그림 1. 월별 웨이퍼 불량 수")
    _figure_page(w, "5. 제조 공정", "제조 공정은 네 단계로 이루어지며 건조 단계 뒤에 수분 검사를 거친다.",
                 _render(_flow, (460, 200), 150), "그림 2. 제조 공정 흐름도")
    w.save()


CASES = [
    {"page": 1, "id": "text_control", "title": "텍스트 페이지 (VLM 미사용, 대조군)",
     "expect": {"label": "text", "facts": ["20 mTorr", "1500W"]}},
    {"page": 2, "id": "scan_text", "title": "스캔 본문",
     "expect": {"label": "scanned", "ocr_text": SCAN_TITLE + "\n" + "\n".join(SCAN_BODY), "title": "비상 대응 절차",
                "facts": ["NF3", "4119", "1 ppm", "SF-07", "24시간"], "no_single_column_table": True}},
    {"page": 3, "id": "scan_table", "title": "스캔 표",
     "expect": {"label": "scanned", "ocr_text": TABLE_TITLE + "\n" + "\n".join(" ".join(r) for r in TABLE_ROWS),
                "table_cells": [v for row in TABLE_ROWS for v in row], "table_columns": 3}},
    {"page": 4, "id": "chart", "title": "막대 차트 그림",
     "expect": {"figure_type": "chart", "figure_facts": ["120", "180", "90", "210", "1월", "4월"], "language": "ko",
                "caption": "그림 1"}},
    {"page": 5, "id": "diagram", "title": "공정 흐름도 그림",
     "expect": {"figure_type": "diagram", "figure_facts": FLOW + ["수분 검사"], "language": "ko", "caption": "그림 2"}},
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pdf = OUT / "vlm_doc.pdf"
    make_pdf(pdf)
    cases = {"name": "합성 5페이지", "documents": [{"file": pdf.name, "cases": CASES}]}
    (OUT / "cases.json").write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(CASES)} cases")


if __name__ == "__main__":
    main()
