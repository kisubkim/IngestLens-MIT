"""Page image with one chunk's regions highlighted, for showing "where the answer came from" outside the app
(the Open WebUI page-image filter deploy/openwebui_page_images.py links these images)."""

import asyncio
import io
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from PIL import Image, ImageDraw

from ..config import settings
from ..db import session
from ..models import Chunk, Document
from ..tools.pdf import open_pdf

router = APIRouter(prefix="/api/chunks", tags=["chunks"])

HIGHLIGHT_STROKE = (237, 115, 13, 230)  # orange outline, 90% opaque
HIGHLIGHT_FILL = (255, 209, 64, 46)     # yellow fill, 18% opaque
PAD = 3  # points around each box


def _render_highlight(pdf_path: str, page: int, boxes: list[list[float]], dpi: int, out: Path) -> None:
    """Render the page, then paint the boxes on the image. The PDF on disk is not changed."""
    with open_pdf(pdf_path) as d:
        if not 0 <= page < d.page_count:
            raise IndexError(page)
        png = d.render(page, dpi)
    out.parent.mkdir(parents=True, exist_ok=True)
    if not boxes:
        out.write_bytes(png)
        return
    img = Image.open(io.BytesIO(png)).convert("RGBA")
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    k = dpi / 72
    for x0, y0, x1, y1 in boxes:
        r = [max(0, (x0 - PAD) * k), max(0, (y0 - PAD) * k), min(img.width - 1, (x1 + PAD) * k), min(img.height - 1, (y1 + PAD) * k)]
        if r[2] > r[0] and r[3] > r[1]:
            draw.rectangle(r, fill=HIGHLIGHT_FILL, outline=HIGHLIGHT_STROKE, width=max(1, round(2 * k)))
    Image.alpha_composite(img, layer).convert("RGB").save(out, "PNG")


@router.get("/{chunk_id}/preview.png")
async def chunk_preview(chunk_id: str, page: int | None = None, dpi: int = 110, highlight: bool = True) -> FileResponse:
    """The chunk's page (0-based; default: its first page) with the chunk's element boxes highlighted.
    `highlight=false` gives the plain page. Cached next to the plain page images, so deleting the document
    removes these too."""
    with session() as s:
        c = s.get(Chunk, chunk_id)
        d = s.get(Document, c.document_id) if c else None
    if not c or not d:
        raise HTTPException(404, "chunk not found")
    if not d.pdf_path:
        raise HTTPException(409, "document not converted")
    on_page = lambda pg: [b["bbox"] for b in (c.bboxes or []) if b.get("page") == pg]  # noqa: E731
    if page is None:
        page = min((b["page"] for b in c.bboxes or []), default=min(c.pages or [0]))
    if page not in (c.pages or []) and not on_page(page):
        raise HTTPException(404, "the chunk is not on that page")
    dpi = max(18, min(dpi, 300))
    out = settings.data_dir / "pages" / d.id / f"chunk_{chunk_id}_{page}_{dpi}{'' if highlight else '_plain'}.png"
    if not out.exists():
        try:
            await asyncio.to_thread(_render_highlight, str(settings.resolve(d.pdf_path)), page,
                                    on_page(page) if highlight else [], dpi, out)
        except IndexError:
            raise HTTPException(404, "page out of range")
    return FileResponse(out, media_type="image/png")
