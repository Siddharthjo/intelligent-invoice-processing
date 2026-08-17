from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from invoice_processing.auth.seed import seed_demo_users


def test_login_succeeds_with_correct_credentials(client: TestClient, db_session: Session):
    seed_demo_users(db_session)
    response = client.post("/auth/login", json={"username": "clerk", "password": "clerk-demo-pass"})

    assert response.status_code == 200
    assert response.json() == {"username": "clerk", "role": "ap_clerk"}
    assert "session_token" in response.cookies


def test_login_returns_the_manager_role_for_the_manager_user(client: TestClient, db_session: Session):
    seed_demo_users(db_session)
    response = client.post("/auth/login", json={"username": "manager", "password": "manager-demo-pass"})

    assert response.status_code == 200
    assert response.json()["role"] == "manager"


def test_login_rejects_wrong_password(client: TestClient, db_session: Session):
    seed_demo_users(db_session)
    response = client.post("/auth/login", json={"username": "clerk", "password": "wrong"})
    assert response.status_code == 401


def test_login_rejects_unknown_username(client: TestClient, db_session: Session):
    seed_demo_users(db_session)
    response = client.post("/auth/login", json={"username": "nobody-at-all", "password": "x"})
    assert response.status_code == 401


def test_me_requires_login(client: TestClient):
    assert client.get("/auth/me").status_code == 401


def test_me_returns_the_logged_in_user(clerk_client: TestClient):
    response = clerk_client.get("/auth/me")
    assert response.status_code == 200
    assert response.json() == {"username": "clerk", "role": "ap_clerk"}


def test_logout_ends_the_session(clerk_client: TestClient):
    assert clerk_client.get("/auth/me").status_code == 200

    logout_response = clerk_client.post("/auth/logout")
    assert logout_response.status_code == 200

    assert clerk_client.get("/auth/me").status_code == 401


def test_logout_without_a_session_is_a_noop(client: TestClient):
    response = client.post("/auth/logout")
    assert response.status_code == 200
