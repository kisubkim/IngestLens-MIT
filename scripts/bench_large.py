"""Large-document benchmark: generate a PDF of a target size and run the full pipeline in-process.

    python scripts/bench_large.py --mb 150 --pages 300 [--vlm-url http://127.0.0.1:8001/v1]

Page mix (repeating): text, text + embedded figure + caption, scanned (full-page image).
Reports per-step seconds, VLM call stats and peak RSS of this process.
"""

import argparse
import asyncio
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

import psutil
import pymupdf
import yaml

ROOT = Path(__file__).resolve().parents[1]
BODY = ("대용량 문서 처리 성능을 측정하기 위한 본문입니다. Retrieval augmented generation pipeline benchmark text. " * 5).strip()


def noise_jpeg(w: int, h: int) -> bytes:
    # Random pixels barely compress, so file size is predictable.
    return pymupdf.Pixmap(pymupdf.csRGB, w, h, os.urandom(w * h * 3), 0).tobytes("jpeg", jpg_quality=90)


def make_pdf(path: Path, pages: int, target_mb: float) -> None:
    images_per_cycle = 2  # figure page + scanned page
    n_images = max(1, pages // 3 * images_per_cycle)
    img_bytes = target_mb * 2**20 / n_images
    # Noise JPEG at quality 90 is ~2.3 bytes per pixel; size the images to hit the target.
    side = int((img_bytes / 2.3 / 1.4) ** 0.5)
    doc = pymupdf.open()
    for i in range(pages):
        page = doc.new_page()
        kind = i % 3
        if kind in (0, 1):
            page.insert_text((72, 80), f"{i + 1}. 섹션 {i + 1}", fontsize=18, fontname="korea")
            page.insert_textbox(pymupdf.Rect(72, 110, 520, 360), BODY, fontsize=10, fontname="korea")
        if kind == 1:
            page.insert_image(pymupdf.Rect(72, 380, 420, 600), stream=noise_jpeg(side, int(side * 1.4)))  # unique: PyMuPDF dedupes identical streams
            page.insert_text((72, 620), f"그림 {i + 1}. 측정 장비 구성", fontsize=9, fontname="korea")
        if kind == 2:
            page.insert_image(page.rect, stream=noise_jpeg(side, int(side * 1.4)))  # unique: PyMuPDF dedupes identical streams
    doc.save(path, garbage=0, deflate=True)
    doc.close()


class PeakRSS(threading.Thread):
    def __init__(self) -> None:
        super().__init__(daemon=True)
        self.peak = 0
        self.stop = False

    def run(self) -> None:
        p = psutil.Process()
        while not self.stop:
            rss = p.memory_info().rss
            for c in p.children(recursive=True):  # parse worker processes
                try:
                    rss += c.memory_info().rss
                except psutil.NoSuchProcess:
                    pass
            self.peak = max(self.peak, rss)
            time.sleep(0.05)


async def run(pdf: Path) -> dict:
    from app.db import init_db, session
    from app.events import bus
    from app.graph.pipeline import run_pipeline
    from app.models import Document, Event, Run
    from sqlalchemy import select

    init_db()
    bus.bind(asyncio.get_running_loop())
    with session() as s:
        doc = Document(filename=pdf.name, sha256="bench", size=pdf.stat().st_size, path=str(pdf))
        s.add(doc)
        s.flush()
        run = Run(document_id=doc.id)
        s.add(run)
        s.flush()
        doc_id, run_id = doc.id, run.id
    try:
        await run_pipeline(run_id, doc_id)
    finally:
        from app.agents.parser import shutdown_pool
        from app.tools import vectorstore

        shutdown_pool()
        vectorstore.close()
    with session() as s:
        r = s.get(Run, run_id)
        steps = {e.step: e.data.get("seconds") for e in s.scalars(select(Event).where(Event.run_id == run_id, Event.type == "step_finished"))}
        return {"status": r.status, "error": r.error, "steps": steps, "summary": r.summary}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mb", type=float, default=150)
    ap.add_argument("--pages", type=int, default=300)
    ap.add_argument("--vlm-url", default="")
    ap.add_argument("--workdir", default="")
    a = ap.parse_args()

    work = Path(a.workdir or tempfile.mkdtemp(prefix="rag-bench-"))
    work.mkdir(parents=True, exist_ok=True)
    pdf = work / f"bench_{a.pages}p_{int(a.mb)}mb.pdf"
    if not pdf.exists():
        t0 = time.perf_counter()
        make_pdf(pdf, a.pages, a.mb)
        print(f"generated {pdf.name}: {pdf.stat().st_size / 2**20:.1f} MB in {time.perf_counter() - t0:.1f}s")

    models = yaml.safe_load((ROOT / "config" / "models.yaml").read_text(encoding="utf-8"))
    models["vlm"]["base_url"] = a.vlm_url
    models["vlm"]["model"] = "mock-vl" if a.vlm_url else models["vlm"]["model"]
    models_file = work / "models.yaml"
    models_file.write_text(yaml.safe_dump(models, allow_unicode=True), encoding="utf-8")
    os.environ["RAG_DATA_DIR"] = str(work / "data")
    os.environ["RAG_MODELS_FILE"] = str(models_file)
    sys.path.insert(0, str(ROOT / "backend"))

    mon = PeakRSS()
    mon.start()
    t0 = time.perf_counter()
    res = asyncio.run(run(pdf))
    total = time.perf_counter() - t0
    mon.stop = True

    parse = res["summary"].get("parse", {})
    print(f"status: {res['status']} {res['error'] or ''}")
    print(f"total: {total:.1f}s   peak RSS (incl. workers): {mon.peak / 2**20:.0f} MB   pdf: {pdf.stat().st_size / 2**20:.1f} MB, {a.pages} pages")
    for step, secs in res["steps"].items():
        print(f"  {step:<9} {secs:>7}s")
    print("  profile:", res["summary"].get("profile", {}).get("label_counts"))
    print("  parse:  ", {k: parse.get(k) for k in ("elements", "vlm_calls", "vlm_errors", "vlm_avg_seconds", "figures_described", "window_prepare_s", "window_vlm_wait_s", "vlm_image_mb")})
    print("  chunk:  ", {k: res["summary"].get("chunk", {}).get(k) for k in ("count", "tokens_avg", "too_short", "too_long")})


if __name__ == "__main__":
    main()
