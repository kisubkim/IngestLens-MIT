from app.config import rules_cfg
from app.tools.figures import attach_captions, empty_cell_ratio, figure_regions
from app.tools.vlm_output import md_to_elements, parse_figure

from .conftest import FIGURE_RECT, gray_image, one_page


def _page_with_figures(tmp_path):
    def draw(w):
        # vector diagram: three boxes joined by lines -> one drawing cluster
        for x in (80, 200, 320):
            w.rect((x, 100, x + 80, 200))
        w.line((160, 150), (200, 150))
        w.line((280, 150), (320, 150))
        w.image(FIGURE_RECT, gray_image(174, 110))
        # small icon: below min_area_ratio
        w.image((500, 700, 520, 720), gray_image(10, 10))
    return one_page(tmp_path / "figures.pdf", draw)


def test_figure_regions_finds_images_and_drawing_clusters(tmp_path):
    doc, page = _page_with_figures(tmp_path)
    regions = figure_regions(page, [], min_area_ratio=0.04, max_regions=4)
    assert [r["source"] for r in regions] == ["drawing", "image"]
    assert regions[1]["bbox"] == [72, 380, 420, 600]
    doc.close()


def test_figure_regions_skips_table_rulings(tmp_path):
    doc, page = _page_with_figures(tmp_path)
    table_bbox = [70, 90, 410, 210]
    assert [r["source"] for r in figure_regions(page, [table_bbox], 0.04, 4)] == ["image"]
    doc.close()


def test_empty_cell_ratio(tmp_path):
    def draw(w):
        for r in range(5):
            w.line((72, 100 + r * 30), (372, 100 + r * 30))
        for c in range(4):
            w.line((72 + c * 100, 100), (72 + c * 100, 220))
        w.text(80, 120, "only", size=9)
        w.text(180, 150, "two", size=9)
    doc, page = one_page(tmp_path / "t.pdf", draw)
    t = page.tables()[0]
    assert empty_cell_ratio(t) > 0.5
    doc.close()


def test_attach_captions_moves_caption_into_figure():
    pattern = rules_cfg()["parse"]["captions"]["pattern"]
    els = [
        {"type": "text", "bbox": [72, 100, 500, 300], "content": "본문"},
        {"type": "figure", "bbox": [72, 380, 420, 600], "content": "diagram text"},
        {"type": "text", "bbox": [72, 610, 300, 622], "content": "그림 1. 시스템 구성도"},
        {"type": "text", "bbox": [72, 700, 300, 712], "content": "그림 2. far away caption"},
    ]
    out = attach_captions(els, pattern, max_gap=40)
    assert [e["content"] for e in out if e["type"] == "text"] == ["본문", "그림 2. far away caption"]
    fig = next(e for e in out if e["type"] == "figure")
    assert fig["meta"]["caption"] == "그림 1. 시스템 구성도"
    assert fig["content"].startswith("**그림 1. 시스템 구성도**")


def test_attach_captions_bracketed_labels():
    """Government reports write captions as [그림 1], <표 1> or 【그림 1】, often above the figure."""
    pattern = rules_cfg()["parse"]["captions"]["pattern"]
    for caption in ("[그림 1] 전국 월별 출생 추이", "<표 2> 시도별 출생아 수", "【그림 3】 흐름도", "(Figure 4) Flow"):
        els = [{"type": "text", "bbox": [72, 300, 400, 312], "content": caption},
               {"type": "figure", "bbox": [72, 320, 420, 500], "content": "chart"}]
        out = attach_captions(els, pattern, max_gap=40)
        assert out[0]["meta"]["caption"] == caption, caption
    els = [{"type": "text", "bbox": [72, 300, 400, 312], "content": "[참고] 그림 1은 예시다"},
           {"type": "figure", "bbox": [72, 320, 420, 500], "content": "chart"}]
    assert len(attach_captions(els, pattern, max_gap=40)) == 2


def test_parse_figure():
    assert parse_figure("TYPE: chart\n| x | y |") == ("chart", "| x | y |")
    assert parse_figure("```markdown\n**TYPE:** Diagram\nA -> B\n```") == ("diagram", "A -> B")
    assert parse_figure("no type line") == ("diagram", "no type line")


def test_md_to_elements_keeps_structure():
    md = "# 제목\n\n첫 문단\n둘째 줄\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n## 소제목\n본문"
    els = md_to_elements(md, [0, 0, 10, 10], "vlm_ocr")
    assert [(e["type"], e["content"].splitlines()[0]) for e in els] == [
        ("title", "제목"), ("text", "첫 문단"), ("table", "| a | b |"), ("title", "소제목"), ("text", "본문")]
