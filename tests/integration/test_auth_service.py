import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from invoice_processing.auth.orm_models import SessionRecord, UserRecord
from invoice_processing.auth.security import hash_password
from invoice_processing.auth.service import (
    create_session,
    delete_session,
    get_user_by_username,
    get_user_for_session,
)
from invoice_processing.domain.enums import UserRole


def _make_user(session: Session, username: str) -> UserRecord:
    user = UserRecord(
        username=username, password_hash=hash_password("pw"), role=UserRole.AP_CLERK
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_get_user_by_username_finds_an_existing_user(db_session: Session):
    username = f"test-user-{uuid.uuid4().hex[:8]}"
    user = _make_user(db_session, username)
    found = get_user_by_username(username, db_session)
    assert found is not None
    assert found.id == user.id


def test_get_user_by_username_returns_none_for_unknown_username(db_session: Session):
    assert get_user_by_username(f"nobody-{uuid.uuid4().hex[:8]}", db_session) is None


def test_create_session_and_look_it_up(db_session: Session):
    user = _make_user(db_session, f"test-user-{uuid.uuid4().hex[:8]}")
    session_record = create_session(user, db_session)

    found = get_user_for_session(session_record.id, db_session)
    assert found is not None
    assert found.id == user.id


def test_get_user_for_session_returns_none_for_unknown_token(db_session: Session):
    assert get_user_for_session("not-a-real-token", db_session) is None


def test_get_user_for_session_returns_none_and_deletes_an_expired_session(db_session: Session):
    user = _make_user(db_session, f"test-user-{uuid.uuid4().hex[:8]}")
    expired = SessionRecord(
        id=f"expired-{uuid.uuid4().hex}",
        user_id=user.id,
        # Must match service.py's naive-UTC convention -- datetime.now() (local time)
        # would be wrong on any machine not already in UTC.
        expires_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1),
    )
    db_session.add(expired)
    db_session.commit()

    assert get_user_for_session(expired.id, db_session) is None
    assert db_session.get(SessionRecord, expired.id) is None


def test_delete_session_removes_it(db_session: Session):
    user = _make_user(db_session, f"test-user-{uuid.uuid4().hex[:8]}")
    session_record = create_session(user, db_session)

    delete_session(session_record.id, db_session)

    assert db_session.get(SessionRecord, session_record.id) is None


def test_delete_session_is_a_noop_for_an_unknown_token(db_session: Session):
    delete_session("not-a-real-token", db_session)  # must not raise
