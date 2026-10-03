"""PyMuPDF helpers: page features for profiling, rule classification, native extraction."""

from collections import Counter

import pymupdf


def _area(r) -> float:
    return max(0.0, (r[2] - r[0])) * max(0.0, (r[3] - r[1]))


def _clip(bbox, page_rect) -> list[float]:
    x0, y0, x1, y1 = bbox
    return [max(x0, page_rect.x0), max(y0, page_rect.y0), min(x1, page_rect.x1), min(y1, page_rect.y1)]


def page_features(page: pymupdf.Page) -> dict:
    rect = page.rect
    page_area = _area(rect) or 1.0

    drawings = len(page.get_drawings())

    # Table detection is the slowest probe; tables need ruling lines, so skip pages without drawings.
    tables, table_area, table_boxes = 0, 0.0, []
    if drawings:
        found = page.find_tables().tables
        tables = len(found)
        table_boxes = [list(t.bbox) for t in found]
        table_area = sum(_area(_clip(b, rect)) for b in table_boxes)

    d = page.get_text("dict")
    text_chars = 0
    table_chars = 0
    text_area = 0.0
    size_hist: Counter = Counter()
    for block in d["blocks"]:
        if block["type"] != 0:
            continue
        text_area += _area(_clip(block["bbox"], rect))
        for line in block["lines"]:
            for span in line["spans"]:
                n = len(span["text"].strip())
                text_chars += n
                if n:
                    size_hist[str(round(span["size"], 1))] += n
                    if any(inside(span["bbox"], b) for b in table_boxes):
                        table_chars += n

    images = page.get_image_info()
    image_area = sum(_area(_clip(i["bbox"], rect)) for i in images)

    return {
        "text_chars": text_chars,
        "text_area_ratio": round(min(text_area / page_area, 1.0), 3),
        "images": len(images),
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
    """Most common span size weighted by characters."""
    if not size_hist:
        return None
    return float(max(size_hist.items(), key=lambda kv: kv[1])[0])


def extract_text_elements(page: pymupdf.Page, heading_min_size: float | None) -> list[dict]:
    """Text blocks in reading order, split where lines switch between heading and body size
    (MuPDF often glues a heading to the paragraph above it). Heading-size runs up to 200 chars are titles."""
    out = []
    for block in page.get_text("dict", sort=True)["blocks"]:
        if block["type"] != 0:
            continue
        groups: list[list] = []  # [is_heading, lines, bbox]
        for line in block["lines"]:
            t = "".join(s["text"] for s in line["spans"]).strip()
            if not t:
                continue
            size = min(s["size"] for s in line["spans"] if s["text"].strip())
            head = heading_min_size is not None and size >= heading_min_size
            if groups and groups[-1][0] == head:
                g = groups[-1]
                g[1].append(t)
                g[2] = [min(g[2][0], line["bbox"][0]), min(g[2][1], line["bbox"][1]), max(g[2][2], line["bbox"][2]), max(g[2][3], line["bbox"][3])]
            else:
                groups.append([head, [t], list(line["bbox"])])
        for head, lines, bbox in groups:
            text = "\n".join(lines)
            out.append({"type": "title" if head and len(text) <= 200 else "text", "bbox": [round(v, 1) for v in bbox], "content": text})
    return out


def inside(inner, outer, tol: float = 2.0) -> bool:
    return inner[0] >= outer[0] - tol and inner[1] >= outer[1] - tol and inner[2] <= outer[2] + tol and inner[3] <= outer[3] + tol


def render_png(page: pymupdf.Page, dpi: int) -> bytes:
    return page.get_pixmap(dpi=dpi).tobytes("png")
