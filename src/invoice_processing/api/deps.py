from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from invoice_processing.auth.orm_models import UserRecord
from invoice_processing.auth.service import SESSION_COOKIE_NAME, get_user_for_session
from invoice_processing.domain.enums import UserRole
from invoice_processing.persistence.db import get_session

SessionDep = Annotated[Session, Depends(get_session)]


def _get_current_user(
    session: SessionDep,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> UserRecord:
    if session_token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not logged in.")
    user = get_user_for_session(session_token, session)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired or invalid.")
    return user


CurrentUser = Annotated[UserRecord, Depends(_get_current_user)]


def _require_manager(current_user: CurrentUser) -> UserRecord:
    if current_user.role != UserRole.MANAGER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Manager role required.")
    return current_user


RequireManager = Annotated[UserRecord, Depends(_require_manager)]
