"""Build evals/samples/: real public documents (selected pages) for evaluation, plus SOURCES.md.

    python scripts/make_sample_set.py [--cache DIR]

Every source is openly licensed (KOGL type 1, CC BY / CC BY-SA, US government work), so the trimmed copies can
live in this public repository with attribution. The committed PDFs are the reference set: Wikipedia articles
change, so re-running this script later can produce different pages and a different dataset version. The committed
files were made with an older tool that also downsampled images; this version copies pages as they are, so
regenerated files can be larger.
Expectations for scripts/eval_vlm.py are in evals/samples/cases.json (written by hand from the pages).
"""

import argparse
import hashlib
import io
import sys
import tempfile
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evals" / "samples"
sys.path.insert(0, str(ROOT / "backend"))
UA = "IngestLens-eval/0.1 (document parsing evaluation; https://github.com/kisubkim/IngestLens-MIT)"

from app.tools.pdfgen import PdfWriter  # noqa: E402
KOSTAT = "https://kostat.go.kr/boardDownload.es?bid=204&list_no=439018&seq=4"
KOSTAT_PAGE = "https://kostat.go.kr/board.es?act=view&bid=204&list_no=439018&mid=a10301010000"
KOGL1 = ("공공누리 제1유형 (출처표시)", "https://www.kogl.or.kr/info/license.do")
CC_BY_SA = ("CC BY-SA 4.0", "https://creativecommons.org/licenses/by-sa/4.0/")
US_GOV = ("미국 연방정부 저작물 (미국 내 저작권 없음)", "https://www.usa.gov/government-copyright")


def wiki(title: str) -> str:
    return "https://ko.wikipedia.org/api/rest_v1/page/pdf/" + urllib.parse.quote(title)


SOURCES = [
    {"id": "ko_text_hunminjeongeum", "kind": "한국어 · 글자 위주", "title": "위키백과 「훈민정음」", "url": wiki("훈민정음"),
     "page_url": "https://ko.wikipedia.org/wiki/훈민정음", "license": CC_BY_SA, "pages": [2, 3, 4, 6],
     "credit": "위키백과 기여자, 「훈민정음」, 한국어 위키백과. 그림은 위키미디어 공용의 각 파일 라이선스를 따른다."},
    {"id": "ko_image_gyeongbokgung", "kind": "한국어 · 사진 위주", "title": "위키백과 「경복궁」", "url": wiki("경복궁"),
     "page_url": "https://ko.wikipedia.org/wiki/경복궁", "license": CC_BY_SA, "pages": [1, 10, 11, 12, 13],
     "credit": "위키백과 기여자, 「경복궁」, 한국어 위키백과. 사진은 위키미디어 공용의 각 파일 라이선스를 따른다."},
    {"id": "ko_chart_population", "kind": "한국어 · 차트 위주 (벡터 SVG 차트)", "title": "위키백과 「대한민국의 인구」", "url": wiki("대한민국의 인구"),
     "page_url": "https://ko.wikipedia.org/wiki/대한민국의_인구", "license": CC_BY_SA, "pages": [1, 4, 5, 6, 7, 9],
     "credit": "위키백과 기여자, 「대한민국의 인구」, 한국어 위키백과. 그래프는 위키미디어 공용의 각 파일 라이선스를 따른다."},
    {"id": "ko_chart_kostat", "kind": "한국어 · 차트 위주 (벡터 차트 + 표)", "title": "국가데이터처 보도자료 「2025년 8월 인구동향」 요약",
     "url": KOSTAT, "page_url": KOSTAT_PAGE, "license": KOGL1, "pages": [5, 6, 8, 9, 10],
     "credit": "국가데이터처, 「2025년 8월 인구동향(출생, 사망, 혼인, 이혼)」 보도자료, 2025-10-29. 일부 페이지 발췌."},
    {"id": "ko_table_kostat", "kind": "한국어 · 표 위주", "title": "국가데이터처 보도자료 「2025년 8월 인구동향」 통계표",
     "url": KOSTAT, "page_url": KOSTAT_PAGE, "license": KOGL1, "pages": [13, 14, 15, 16],
     "credit": "국가데이터처, 「2025년 8월 인구동향(출생, 사망, 혼인, 이혼)」 보도자료, 2025-10-29. 일부 페이지 발췌."},
    {"id": "ko_scan_kostat", "kind": "한국어 · 스캔 (모사)", "title": "국가데이터처 보도자료 「2025년 8월 인구동향」 일부를 스캔 이미지로 변환",
     "url": KOSTAT, "page_url": KOSTAT_PAGE, "license": KOGL1, "pages": [2, 6, 13], "scan": True,
     "credit": "국가데이터처, 「2025년 8월 인구동향(출생, 사망, 혼인, 이혼)」 보도자료, 2025-10-29. 일부 페이지를 흑백 이미지로 변환(변경함)."},
    {"id": "ko_mixed_seoul", "kind": "한국어 · 혼합 (사진, 지도, 표, 차트)", "title": "위키백과 「서울특별시」", "url": wiki("서울특별시"),
     "page_url": "https://ko.wikipedia.org/wiki/서울특별시", "license": CC_BY_SA, "pages": [1, 6, 7, 11, 15],
     "credit": "위키백과 기여자, 「서울특별시」, 한국어 위키백과. 그림은 위키미디어 공용의 각 파일 라이선스를 따른다."},
    {"id": "en_scan_naca1135", "kind": "영어 · 실제 스캔 (수식, 표, 차트)", "title": "NACA Report 1135, Equations, Tables, and Charts for Compressible Flow (1953)",
     "url": "https://ntrs.nasa.gov/api/citations/19930091059/downloads/19930091059.pdf",
     "page_url": "https://ntrs.nasa.gov/citations/19930091059", "license": US_GOV, "pages": [1, 2, 14, 22, 42, 57],
     "credit": "Ames Research Staff, NACA Report 1135, 1953. NASA Technical Reports Server (Public Use Permitted)."},
    {"id": "en_mixed_nist", "kind": "영어 · 혼합 (본문, 다이어그램)", "title": "NIST SP 800-207, Zero Trust Architecture (2020)",
     "url": "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-207.pdf",
     "page_url": "https://doi.org/10.6028/NIST.SP.800-207", "license": US_GOV, "pages": [1, 10, 14, 23, 25, 26],
     "credit": "S. Rose, O. Borchert, S. Mitchell, S. Connelly, NIST SP 800-207, 2020."},
    {"id": "en_paper_docling", "kind": "영어 · 논문 (그림, 표, 코드)", "title": "Docling Technical Report (arXiv:2408.09869v5)",
     "url": "https://arxiv.org/pdf/2408.09869v5", "page_url": "https://arxiv.org/abs/2408.09869",
     "license": ("CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/"), "pages": [1, 2, 3, 4, 5, 6],
     "credit": "C. Auer et al., Docling Technical Report, arXiv:2408.09869, 2024."},
]


def fetch(url: str, dest: Path) -> Path:
    if not dest.exists():
        headers = {"User-Agent": UA}
        if url == KOSTAT:
            headers["Referer"] = KOSTAT_PAGE
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=300) as r:
            dest.write_bytes(r.read())
    return dest


def build(src: Path, spec: dict, out: Path) -> int:
    s = pdfium.PdfDocument(src)
    try:
        if not spec.get("scan"):
            doc = pdfium.PdfDocument.new()
            doc.import_pages(s, [p - 1 for p in spec["pages"]])
            doc.save(out)
            n = len(doc)
            doc.close()
            return n
        # A grey JPEG of the page and nothing else: no text layer, like a cheap office scanner.
        w = PdfWriter(out)
        for p in spec["pages"]:
            page = s[p - 1]
            width, height = page.get_size()
            buf = io.BytesIO()
            page.render(scale=150 / 72, grayscale=True).to_pil().save(buf, "JPEG", quality=60)
            page.close()
            w.new_page(width, height)
            w.image((0, 0, width, height), buf.getvalue())
        w.save()
        return len(spec["pages"])
    finally:
        s.close()


def sources_md(rows: list[tuple[dict, int, int]]) -> str:
    out = ["# 평가용 실제 문서", "",
           f"`scripts/make_sample_set.py`가 아래 원본에서 일부 페이지를 골라 만든다. 받은 날: {date.today()}.",
           "모두 출처를 밝히면 재배포와 변경이 허용되는 자료다. 각 파일은 원본의 라이선스를 따르며, 이 저장소의 MIT 라이선스가 적용되지 않는다.",
           "파일 크기를 줄이려고 이미지 해상도를 낮췄다(스캔 모사 파일은 페이지 전체를 흑백 이미지로 바꿨다).", "",
           "| 파일 | 유형 | 원본 | 사용한 페이지(원본 기준) | 라이선스 | 출처 표시 |", "|---|---|---|---|---|---|"]
    for spec, n, size in rows:
        name, url = spec["license"]
        pages = ", ".join(map(str, spec["pages"]))
        out.append(f"| `{spec['id']}.pdf` ({n}p, {size // 1024}KB) | {spec['kind']} | [{spec['title']}]({spec['page_url']}) | {pages} | "
                   f"[{name}]({url}) | {spec['credit']} |")
    out += ["", "위키백과 문서는 [REST API PDF 변환](https://ko.wikipedia.org/api/rest_v1/)으로 받았다. 원문이 계속 바뀌므로 커밋된 PDF가 기준이다.", ""]
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", type=Path, help="where downloaded originals are kept (default: a temp dir)")
    a = ap.parse_args()
    cache = a.cache or Path(tempfile.mkdtemp(prefix="rag-samples-"))
    cache.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for spec in SOURCES:
        src = fetch(spec["url"], cache / (hashlib.sha1(spec["url"].encode()).hexdigest()[:12] + ".pdf"))
        out = OUT / f"{spec['id']}.pdf"
        n = build(src, spec, out)
        rows.append((spec, n, out.stat().st_size))
        print(f"{out.relative_to(ROOT)}: {n} pages, {out.stat().st_size // 1024} KB")
    (OUT / "SOURCES.md").write_text(sources_md(rows), encoding="utf-8")


if __name__ == "__main__":
    main()
