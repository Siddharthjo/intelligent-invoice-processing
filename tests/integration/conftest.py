from collections.abc import Generator

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from invoice_processing.persistence.db import SessionLocal, engine


@pytest.fixture(scope="module")
def db_session() -> Generator[Session, None, None]:
    """A session against the real, Alembic-migrated dev/test database.

    Deliberately does NOT create/drop tables here: this fixture runs against
    a shared, persistent database (not an ephemeral per-test one), so schema
    management belongs to `alembic upgrade head`, not test setup/teardown.
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001  (any connection failure means "skip")
        pytest.skip(f"Postgres is not reachable at the configured DATABASE_URL: {exc}")

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
