import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from invoice_processing.persistence.db import Base


class UserRecord(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(unique=True)
    password_hash: Mapped[str]
    role: Mapped[str]

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class SessionRecord(Base):
    """Server-side session, keyed by the opaque token that's also the cookie value.

    Demo-grade: no session rotation on privilege change, no "log out everywhere"
    UI, no CSRF protection on the state-changing endpoints this session guards.
    """

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    expires_at: Mapped[datetime]

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
