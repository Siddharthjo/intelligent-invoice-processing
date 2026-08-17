from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from invoice_processing.auth.orm_models import SessionRecord, UserRecord
from invoice_processing.auth.security import generate_session_token
from invoice_processing.config import get_settings

SESSION_COOKIE_NAME = "session_token"


def _now_naive_utc() -> datetime:
    # The rest of this codebase's timestamp columns are naive (populated via Postgres
    # func.now()), so comparisons here stay naive-vs-naive too rather than mixing in an
    # aware datetime and risking a TypeError on comparison.
    return datetime.now(UTC).replace(tzinfo=None)


def get_user_by_username(username: str, session: Session) -> UserRecord | None:
    return session.query(UserRecord).filter(UserRecord.username == username).first()


def create_session(user: UserRecord, session: Session) -> SessionRecord:
    settings = get_settings()
    record = SessionRecord(
        id=generate_session_token(),
        user_id=user.id,
        expires_at=_now_naive_utc() + timedelta(hours=settings.session_ttl_hours),
    )
    session.add(record)
    session.commit()
    return record


def get_user_for_session(token: str, session: Session) -> UserRecord | None:
    record = session.get(SessionRecord, token)
    if record is None:
        return None
    if record.expires_at < _now_naive_utc():
        session.delete(record)
        session.commit()
        return None
    return session.get(UserRecord, record.user_id)


def delete_session(token: str, session: Session) -> None:
    record = session.get(SessionRecord, token)
    if record is not None:
        session.delete(record)
        session.commit()
