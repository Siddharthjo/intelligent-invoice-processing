import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from invoice_processing.api.routes.gmail import router as gmail_router
from invoice_processing.api.routes.invoices import router as invoices_router
from invoice_processing.config import get_settings
from invoice_processing.intake.gmail import poll_inbox
from invoice_processing.persistence.db import SessionLocal

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"


class NoCacheStaticFiles(StaticFiles):
    """This demo page is under active iteration -- always serve the latest file on a
    normal reload rather than letting the browser's heuristic cache mask new changes."""

    def file_response(self, *args: Any, **kwargs: Any) -> Any:
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-store"
        return response


def _run_scheduled_gmail_poll() -> None:
    session = SessionLocal()
    try:
        result = poll_inbox(session)
        logger.info(
            "Scheduled Gmail poll: checked=%d processed=%d failed=%d",
            result.checked_messages,
            len(result.processed_invoice_ids),
            len(result.failed_message_ids),
        )
    except Exception:
        logger.exception("Scheduled Gmail poll failed")
    finally:
        session.close()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    scheduler: BackgroundScheduler | None = None
    # In-process polling only fires while a replica is actually running. On a
    # scale-to-zero deployment (see the Azure Container App config) an idle app has no
    # running replica, so this silently never fires -- POST /gmail/check-now is the
    # mechanism that reliably works there. This scheduler is for continuously-running
    # deployments (local dev, or min-replicas >= 1).
    if settings.gmail_enabled and settings.gmail_poll_interval_minutes:
        scheduler = BackgroundScheduler()
        scheduler.add_job(_run_scheduled_gmail_poll, "interval", minutes=settings.gmail_poll_interval_minutes)
        scheduler.start()
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)


app = FastAPI(title="Intelligent Invoice Processing", version="0.1.0", lifespan=lifespan)
app.include_router(invoices_router)
app.include_router(gmail_router)
app.mount("/ui", NoCacheStaticFiles(directory=STATIC_DIR, html=True), name="ui")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
