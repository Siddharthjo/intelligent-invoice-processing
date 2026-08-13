from fastapi import FastAPI

from invoice_processing.api.routes.invoices import router as invoices_router

app = FastAPI(title="Intelligent Invoice Processing", version="0.1.0")
app.include_router(invoices_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
