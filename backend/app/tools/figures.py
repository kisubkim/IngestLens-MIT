"""Figure regions, captions and table quality: decides what gets sent to the VLM and where it lands on the page."""

import re

import pymupdf


def _area(b) -> float:
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def _intersect(a, b) -> list[float]:
    return [max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])]


def _overlap_ratio(a, b) -> float:
    """Share of a covered by b."""
    return _area(_intersect(a, b)) / (_area(a) or 1.0)


def _union(a, b) -> list[float]:
    return [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]


def figure_regions(page: pymupdf.Page, table_bboxes: list[list[float]], min_area_ratio: float, max_regions: int) -> list[dict]:
    """Embedded images and vector-drawing clusters large enough to be figures, merged when they overlap.
    Drawing clusters that are table ruling lines are dropped."""
    rect = page.rect
    page_area = _area(rect) or 1.0
    cands: list[dict] = []
    for info in page.get_image_info():
        b = _intersect(list(info["bbox"]), list(rect))
        if _area(b) / page_area >= min_area_ratio:
            cands.append({"bbox": b, "source": "image"})
    for r in page.cluster_drawings():
        b = _intersect(list(r), list(rect))
        if _area(b) / page_area < min_area_ratio:
            continue
        if any(_overlap_ratio(b, t) > 0.5 for t in table_bboxes):
            continue
        cands.append({"bbox": b, "source": "drawing"})

    merged: list[dict] = []
    for c in sorted(cands, key=lambda c: -_area(c["bbox"])):
        for m in merged:
            if _area(_intersect(m["bbox"], c["bbox"])) > 0:
                m["bbox"] = _union(m["bbox"], c["bbox"])
                if c["source"] not in m["source"]:
                    m["source"] += "+" + c["source"]
                break
        else:
            merged.append(dict(c))
    merged = merged[:max_regions]
    for m in merged:
        m["bbox"] = [round(v, 1) for v in m["bbox"]]
        m["area_ratio"] = round(_area(m["bbox"]) / page_area, 3)
    return sorted(merged, key=lambda m: (m["bbox"][1], m["bbox"][0]))


def render_clip(page: pymupdf.Page, bbox: list[float], dpi: int, fmt: str, pad: float = 6) -> bytes:
    clip = pymupdf.Rect(bbox) + (-pad, -pad, pad, pad)
    clip &= page.rect
    pix = page.get_pixmap(dpi=dpi, clip=clip)
    if fmt == "jpeg":
        if pix.alpha:
            pix = pymupdf.Pixmap(pix, 0)
        return pix.tobytes("jpeg", jpg_quality=85)
    return pix.tobytes("png")


def empty_cell_ratio(table) -> float:
    rows = table.extract()
    cells = [c for row in rows for c in row]
    if not cells:
        return 1.0
    return round(sum(1 for c in cells if c is None or not str(c).strip()) / len(cells), 3)


def attach_captions(elements: list[dict], pattern: str, max_gap: float) -> list[dict]:
    """Move a caption-looking text block next to a figure/table into that element. Returns the new list."""
    rx = re.compile(pattern, re.I)
    targets = [e for e in elements if e["type"] in ("figure", "table")]
    used: set[int] = set()
    for t in targets:
        tb = t["bbox"]
        best, best_gap = None, max_gap + 1
        for i, e in enumerate(elements):
            if i in used or e["type"] not in ("text", "title") or not rx.match(e["content"].strip()):
                continue
            eb = e["bbox"]
            if min(eb[2], tb[2]) - max(eb[0], tb[0]) <= 0:  # no horizontal overlap
                continue
            gap = eb[1] - tb[3] if eb[1] >= tb[3] else tb[1] - eb[3]
            if -2 <= gap < best_gap:
                best, best_gap = i, gap
        if best is not None:
            used.add(best)
            caption = elements[best]["content"].strip()
            t.setdefault("meta", {})["caption"] = caption
            t["content"] = f"**{caption}**\n\n{t['content']}"
    return [e for i, e in enumerate(elements) if i not in used]
