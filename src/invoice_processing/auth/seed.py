from sqlalchemy.orm import Session

from invoice_processing.auth.orm_models import UserRecord
from invoice_processing.auth.security import hash_password
from invoice_processing.domain.enums import UserRole

# Fixed, well-known demo credentials -- intentional for a demo app meant to be logged
# into without digging through server logs first. Not meant to gate anything sensitive;
# this is mock data throughout. Worth a conscious decision, not an assumption, before
# this lands on a public deployment -- see the seeding summary printed by main().
_DEMO_USERS = [
    {"username": "clerk", "password": "clerk-demo-pass", "role": UserRole.AP_CLERK},
    {"username": "manager", "password": "manager-demo-pass", "role": UserRole.MANAGER},
]


def seed_demo_users(session: Session) -> None:
    if session.query(UserRecord).count() > 0:
        return
    for spec in _DEMO_USERS:
        session.add(
            UserRecord(
                username=spec["username"],
                password_hash=hash_password(spec["password"]),
                role=spec["role"],
            )
        )
    session.commit()


def main() -> None:
    from invoice_processing.persistence.db import SessionLocal

    session = SessionLocal()
    try:
        seed_demo_users(session)
        print("Demo users seeded (or already present).")
        print("Fixed demo credentials -- not meant for anything beyond local/demo use:")
        for spec in _DEMO_USERS:
            print(f"  {spec['username']} / {spec['password']}  ({spec['role'].value})")
    finally:
        session.close()


if __name__ == "__main__":
    main()
