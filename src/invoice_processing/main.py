from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from invoice_processing.api.routes.invoices import router as invoices_router

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"


class NoCacheStaticFiles(StaticFiles):
    """This demo page is under active iteration -- always serve the latest file on a
    normal reload rather than letting the browser's heuristic cache mask new changes."""

    def file_response(self, *args: Any, **kwargs: Any) -> Any:
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-store"
        return response


app = FastAPI(title="Intelligent Invoice Processing", version="0.1.0")
app.include_router(invoices_router)
app.mount("/ui", NoCacheStaticFiles(directory=STATIC_DIR, html=True), name="ui")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
