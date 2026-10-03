from app.config import rules_cfg
from app.tools.pdf import classify, open_pdf, page_features

from .conftest import one_page


def test_page_labels(sample_pdf):
    rules = rules_cfg()["profiler"]
    with open_pdf(sample_pdf) as doc:
        labels = [classify(page_features(p), rules) for p in doc.pages()]
    assert [c["label"] for c in labels] == ["text", "text", "table", "diagram", "scanned", "text"]
    for c in labels:
        assert 0 < c["confidence"] <= 1
        assert c["rule_id"]


def test_classify_reports_evidence():
    f = {"text_chars": 10, "image_area_ratio": 0.9, "tables": 0, "table_area_ratio": 0, "drawings": 0}
    c = classify(f, rules_cfg()["profiler"])
    assert c["rule_id"] == "scanned"
    assert c["conditions"]["max_text_chars"] == {"threshold": 50, "actual": 10}


def test_small_table_page_is_table(tmp_path):
    """M6 regression: a page that is only a small table (13% of the page area) used to fall through to mixed."""
    def draw(w):
        w.text(72, 70, "Utilization", size=18)
        for r in range(6):
            w.line((72, 100 + r * 30), (522, 100 + r * 30))
        for c in range(4):
            w.line((72 + c * 150, 100), (72 + c * 150, 250))
        for r in range(5):
            for c in range(3):
                w.text(78 + c * 150, 120 + r * 30, f"r{r}c{c} value", size=10)
    doc, page = one_page(tmp_path / "t.pdf", draw)
    f = page_features(page)
    doc.close()
    assert f["table_area_ratio"] < 0.3 and f["table_text_share"] > 0.5
    assert classify(f, rules_cfg()["profiler"])["rule_id"] == "table_text_share"
