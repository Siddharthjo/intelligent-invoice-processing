FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
      tesseract-ocr poppler-utils \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "poetry>=2.0,<3.0"

WORKDIR /app
COPY pyproject.toml poetry.lock README.md ./
COPY src ./src
COPY evals ./evals
COPY static ./static
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini
COPY --from=frontend-build /app/static/react ./static/react

RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-interaction --no-ansi

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && seed-mock-erp && seed-demo-users && uvicorn invoice_processing.main:app --host 0.0.0.0 --port 8000"]
