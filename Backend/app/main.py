from __future__ import annotations

from contextlib import asynccontextmanager
import asyncio
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api.router import compat_router, router
from .api.targets import router as targets_router, v1_router as monitoring_targets_router
from .api.operations import router as operations_router
from .api.topology import router as topology_router
from .database import initialize_database
from .seed import seed_database
from .services.scheduler import monitoring_loop

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize persistent storage and first-run sample data."""
    initialize_database()
    seed_database()
    stop_event = asyncio.Event()
    task = asyncio.create_task(monitoring_loop(stop_event))
    try:
        yield
    finally:
        stop_event.set()
        await task


app = FastAPI(
    title="ForgeOS",
    version="0.1.0",
    description="IT Operations data entry and inventory platform.",
    lifespan=lifespan,
)
app.include_router(router)
app.include_router(compat_router)
app.include_router(targets_router)
app.include_router(monitoring_targets_router)
app.include_router(operations_router)
app.include_router(topology_router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    """Serve the ForgeOS dashboard."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/people", include_in_schema=False)
@app.get("/assets", include_in_schema=False)
@app.get("/history", include_in_schema=False)
@app.get("/reports", include_in_schema=False)
@app.get("/monitoring", include_in_schema=False)
@app.get("/execution", include_in_schema=False)
@app.get("/security", include_in_schema=False)
@app.get("/import", include_in_schema=False)
@app.get("/dashboard", include_in_schema=False)
@app.get("/preferences", include_in_schema=False)
@app.get("/warehouse", include_in_schema=False)
@app.get("/references", include_in_schema=False)
def dashboard_section() -> FileResponse:
    """Serve the SPA shell for dashboard deep links."""
    return FileResponse(STATIC_DIR / "index.html")
