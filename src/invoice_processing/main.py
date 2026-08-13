from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from invoice_processing.api.routes.invoices import router as invoices_router

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"

app = FastAPI(title="Intelligent Invoice Processing", version="0.1.0")
app.include_router(invoices_router)
app.mount("/ui", StaticFiles(directory=STATIC_DIR, html=True), name="ui")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
