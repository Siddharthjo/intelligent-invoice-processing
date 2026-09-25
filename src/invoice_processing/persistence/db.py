from collections.abc import Generator

from sqlalchemy import String, create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from invoice_processing.config import get_settings


@compiles(String, "hana")
def _compile_hana_string(type_, compiler, **kw):
    # Models and migrations use length-less String() (unbounded on Postgres), but HANA
    # reads a bare NVARCHAR as NVARCHAR(1). 5000 is HANA's NVARCHAR maximum.
    if type_.length is None:
        return "NVARCHAR(5000)"
    return compiler.visit_string(type_, **kw)


class Base(DeclarativeBase):
    pass


engine = create_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
