from fastapi import APIRouter, Cookie, HTTPException, Response, status

from invoice_processing.api.deps import CurrentUser, SessionDep
from invoice_processing.api.schemas import LoginRequest, UserOut
from invoice_processing.auth.security import verify_password
from invoice_processing.auth.service import (
    SESSION_COOKIE_NAME,
    create_session,
    delete_session,
    get_user_by_username,
)
from invoice_processing.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=UserOut)
async def login(body: LoginRequest, response: Response, session: SessionDep) -> UserOut:
    user = get_user_by_username(body.username, session)
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password.")

    settings = get_settings()
    session_record = create_session(user, session)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        session_record.id,
        httponly=True,
        samesite="lax",
        secure=settings.session_cookie_secure,
        max_age=settings.session_ttl_hours * 3600,
    )
    return UserOut(username=user.username, role=user.role)


@router.post("/logout")
async def logout(
    response: Response,
    session: SessionDep,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> dict:
    if session_token:
        delete_session(session_token, session)
    response.delete_cookie(SESSION_COOKIE_NAME)
    return {"logged_out": True}


@router.get("/me", response_model=UserOut)
async def me(current_user: CurrentUser) -> UserOut:
    return UserOut(username=current_user.username, role=current_user.role)
