"""Build the synthetic evaluation set in evals/synthetic/ (documents + page labels + queries with answers).

    python scripts/make_eval_set.py

It exists so the evaluation scripts run out of the box. Replace or extend it with real, hand-labeled
documents in the same JSON formats (see evals/README.md) to tune on data that matters.
"""

import json
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evals" / "synthetic"
sys.path.insert(0, str(ROOT / "backend"))

from tests.office_fixtures import make_docx, make_pptx, make_xlsx  # noqa: E402

FILLER = "이 절의 내용은 정기 교육 자료에도 포함되며 담당자는 변경 사항을 공지해야 한다. "
SECTIONS = [
    ("1. 냉각 시스템", "냉각수 온도는 18도에서 22도 사이로 유지하며, 펌프 압력이 3.5 bar 이하로 떨어지면 경보가 발생한다."),
    ("2. 전원 공급", "주 전원은 380V 3상이며, UPS는 정전 시 15분 동안 장비를 유지한다."),
    ("3. 진공 챔버", "챔버 진공도는 1e-6 Torr 이하를 목표로 하며, 리크 테스트는 매주 월요일에 실시한다."),
    ("4. 가스 공급", "N2 가스 순도는 99.999% 이상이어야 하고, 공급 라인 필터는 분기마다 교체한다."),
    ("5. 안전 수칙", "작업자는 방진복과 보안경을 착용하며, 비상 정지 버튼은 장비 전면 좌측에 있다."),
    ("6. 알람 코드", "E-201은 온도 과열, E-305는 진공 이상, E-410은 통신 두절을 의미한다."),
    ("7. 유지보수", "배기 필터는 500시간마다 교체하고, 교체 이력은 MES에 기록한다."),
    ("8. 데이터 수집", "센서 데이터는 1초 간격으로 수집되어 PC B의 계측 서버에 저장된다."),
]


def _text_page(doc, title, fact):
    page = doc.new_page()
    page.insert_text((72, 80), title, fontsize=18, fontname="korea")
    body = FILLER * 2 + fact + " " + FILLER * 3
    rc = page.insert_textbox(pymupdf.Rect(72, 110, 520, 500), body, fontsize=10, fontname="korea")
    assert rc >= 0, f"text overflow on {title}"


def make_manual(path: Path) -> dict:
    doc = pymupdf.open()
    labels = {}
    for i, (t, f) in enumerate(SECTIONS, start=1):
        _text_page(doc, t, f)
        labels[str(i)] = "text"

    page = doc.new_page()  # 9: table
    page.insert_text((72, 70), "9. 분기별 가동률", fontsize=18, fontname="korea")
    rows = [["구분", "가동률", "비가동 사유"], ["1분기", "92.1%", "정기 점검"], ["2분기", "88.4%", "펌프 교체"], ["3분기", "95.0%", "없음"], ["4분기", "90.7%", "전원 공사"]]
    x0, y0, cw, rh = 72, 100, 150, 30
    for r in range(len(rows) + 1):
        page.draw_line((x0, y0 + r * rh), (x0 + 3 * cw, y0 + r * rh))
    for c in range(4):
        page.draw_line((x0 + c * cw, y0), (x0 + c * cw, y0 + len(rows) * rh))
    for r, row in enumerate(rows):
        for c, v in enumerate(row):
            page.insert_text((x0 + c * cw + 6, y0 + r * rh + 20), v, fontsize=10, fontname="korea")
    labels["9"] = "table"

    page = doc.new_page()  # 10: vector diagram
    for i in range(150):
        x, y = 60 + (i % 15) * 32, 100 + (i // 15) * 50
        page.draw_rect(pymupdf.Rect(x, y, x + 22, y + 22))
    page.insert_text((72, 700), "배관 연결도", fontsize=10, fontname="korea")
    labels["10"] = "diagram"

    page = doc.new_page()  # 11: scanned (image only)
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 300, 420), 0)
    pix.set_rect(pix.irect, (235, 235, 230))
    page.insert_image(page.rect, pixmap=pix)
    labels["11"] = "scanned"

    page = doc.new_page()  # 12: text + figure + caption
    page.insert_text((72, 80), "10. 냉각 계통", fontsize=18, fontname="korea")
    page.insert_textbox(pymupdf.Rect(72, 110, 520, 360), FILLER * 4, fontsize=10, fontname="korea")
    fig = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 348, 220), 0)
    fig.set_rect(fig.irect, (180, 200, 230))
    page.insert_image(pymupdf.Rect(72, 380, 420, 600), pixmap=fig)
    page.insert_text((72, 620), "그림 1. 냉각 계통도", fontsize=9, fontname="korea")
    labels["12"] = "text"

    doc.save(path)
    return labels


QUERIES = {
    "manual.pdf": [
        {"q": "냉각수 온도 유지 범위", "pages": [1], "kind": "lexical"},
        {"q": "쿨링 워터를 몇 도로 관리해야 하나", "pages": [1], "kind": "paraphrase"},
        {"q": "UPS 정전 유지 시간", "pages": [2], "kind": "lexical"},
        {"q": "전기가 끊겼을 때 장비가 버티는 시간", "pages": [2], "kind": "paraphrase"},
        {"q": "리크 테스트 주기", "pages": [3], "kind": "lexical"},
        {"q": "누설 검사는 언제 하나", "pages": [3], "kind": "paraphrase"},
        {"q": "N2 가스 순도 기준", "pages": [4], "kind": "lexical"},
        {"q": "비상 정지 버튼 위치", "pages": [5], "kind": "lexical"},
        {"q": "작업자가 입어야 하는 보호 장비", "pages": [5], "kind": "paraphrase"},
        {"q": "E-305 알람 의미", "pages": [6], "kind": "lexical"},
        {"q": "배기 필터 교체 주기", "pages": [7], "kind": "lexical"},
        {"q": "센서 데이터 수집 간격", "pages": [8], "kind": "lexical"},
        {"q": "측정값은 어디에 저장되나", "pages": [8], "kind": "paraphrase"},
        {"q": "2분기 가동률", "pages": [9], "kind": "lexical"},
        {"q": "가동률이 가장 낮은 분기와 이유", "pages": [9], "kind": "paraphrase"},
        {"q": "냉각 계통도 그림", "pages": [12], "kind": "lexical"},
    ],
    "deck.pptx": [
        {"q": "3월 생산량", "pages": [2], "kind": "lexical"},
        {"q": "발표에서 배경을 설명하는 슬라이드", "pages": [1], "kind": "paraphrase"},
        {"q": "압력 점검 결과", "pages": [3], "kind": "lexical"},
    ],
    "guide.docx": [
        {"q": "온도 점검 주기와 기준", "text": "25±2", "kind": "lexical"},
        {"q": "설치 전에 준비할 것", "text": "전원 케이블", "kind": "paraphrase"},
    ],
    "sheet.xlsx": [
        {"q": "장비별 평균 온도 요약", "text": "평균 온도", "kind": "lexical"},
    ],
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    labels = make_manual(OUT / "manual.pdf")
    make_pptx(OUT / "deck.pptx")
    make_docx(OUT / "guide.docx")
    make_xlsx(OUT / "sheet.xlsx", rows=60)
    (OUT / "profile_labels.json").write_text(json.dumps(
        {"documents": [{"file": "manual.pdf", "pages": labels}]}, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "retrieval.json").write_text(json.dumps(
        {"documents": [{"file": f, "queries": q} for f, q in QUERIES.items()]}, ensure_ascii=False, indent=2), encoding="utf-8")
    n_q = sum(len(q) for q in QUERIES.values())
    print(f"wrote {OUT.relative_to(ROOT)}: 4 documents, {len(labels)} labeled pages, {n_q} queries")


if __name__ == "__main__":
    main()
