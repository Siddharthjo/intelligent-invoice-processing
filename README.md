# Intelligent Invoice Processing

Vertical slice 1: **PDF invoice → extraction → canonical `Invoice` (Pydantic) → deterministic validation → PostgreSQL.**

No agents, RAG, Kafka, frontend, cloud, or SAP integration yet — those come in later slices.

## Architecture

```
src/invoice_processing/
├── main.py            # FastAPI app
├── config.py           # settings (env-driven)
├── api/                 # HTTP boundary: routes, request/response schemas
├── domain/               # canonical Invoice/LineItem/Party Pydantic models
├── extraction/            # PDF -> raw text/tables (text-layer + OCR fallback)
├── parsing/                # raw text/tables -> domain.Invoice (regex/heuristics)
├── validation/              # deterministic business rules over domain.Invoice
├── persistence/              # SQLAlchemy ORM + repository + Postgres
├── pipeline/                  # orchestrates extract -> parse -> validate -> persist
└── cli.py                      # local CLI entrypoint
```

## Prerequisites

- Python 3.11
- [Poetry](https://python-poetry.org/) 2.x
- Docker (for local Postgres via `docker-compose`)
- For OCR fallback: `brew install tesseract poppler`

## Setup

```bash
poetry install
cp .env.example .env
docker compose up -d
poetry run alembic upgrade head
```

## Run

```bash
poetry run uvicorn invoice_processing.main:app --reload
```

Or process a single PDF from the command line without the API:

```bash
poetry run process-invoice path/to/invoice.pdf
```

## Test

```bash
poetry run pytest
```
