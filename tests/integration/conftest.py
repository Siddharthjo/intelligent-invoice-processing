from collections.abc import Generator

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from invoice_processing.persistence import orm_models  # noqa: F401  (registers models on Base.metadata)
from invoice_processing.persistence.db import Base, SessionLocal, engine


@pytest.fixture(scope="module")
def db_session() -> Generator[Session, None, None]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001  (any connection failure means "skip")
        pytest.skip(f"Postgres is not reachable at the configured DATABASE_URL: {exc}")

    Base.metadata.create_all(engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
