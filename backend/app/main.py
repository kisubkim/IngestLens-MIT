import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import update

from .agents.parser import shutdown_pool
from .api import documents, ingest, runs, search, settings as settings_api
from .config import ROOT
from .db import init_db, session
from .events import bus
from .models import Run, now
from .tools import vectorstore


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    bus.bind(asyncio.get_running_loop())
    # In-process runs do not survive a restart; mark them failed instead of leaving them "running".
    with session() as s:
        s.execute(update(Run).where(Run.status.in_(["queued", "running"])).values(status="failed", error="server restarted", finished_at=now()))
    yield
    shutdown_pool()
    vectorstore.close()


app = FastAPI(title="IngestLens", lifespan=lifespan)
app.include_router(documents.router)
app.include_router(runs.router)
app.include_router(search.router)
app.include_router(ingest.router)
app.include_router(settings_api.router)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


_dist = ROOT / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="ui")
