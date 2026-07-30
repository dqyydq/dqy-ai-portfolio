import asyncio
import uuid

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.config import get_settings
from app.core.security import ALGORITHM
from app.db.database import close_database, session_factory
from app.main import app
from app.models.user import User


async def _delete_test_user(email: str) -> None:
    try:
        async with session_factory() as session:
            await session.execute(delete(User).where(User.email == email))
            await session.commit()
    finally:
        await close_database()


def test_register_user() -> None:
    email = f"api-test-{uuid.uuid4()}@example.com"
    payload = {
        "email": email,
        "user_name": f"user_{uuid.uuid4().hex[:12]}",
        "password": "correct horse battery staple",
    }

    try:
        with TestClient(app) as client:
            response = client.post("/auth/register", json=payload)

        assert response.status_code == 201
        body = response.json()
        assert body["email"] == payload["email"]
        assert body["user_name"] == payload["user_name"]
        assert "id" in body
        assert "created_at" in body
        assert "password" not in body
        assert "password_hash" not in body
    finally:
        asyncio.run(_delete_test_user(email))


def test_duplicate_registration_returns_conflict() -> None:
    email = f"duplicate-{uuid.uuid4()}@example.com"
    payload = {
        "email": email,
        "user_name": f"user_{uuid.uuid4().hex[:12]}",
        "password": "correct horse battery staple",
    }

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            assert client.post("/auth/register", json=payload).status_code == 201
            response = client.post("/auth/register", json=payload)

        assert response.status_code == 409
        assert response.json()["detail"] == "Email or user name already registered"
    finally:
        asyncio.run(_delete_test_user(email))


def test_login_returns_token_for_valid_credentials() -> None:
    email = f"login-api-{uuid.uuid4()}@example.com"
    password = "correct horse battery staple"
    register_payload = {
        "email": email,
        "user_name": f"user_{uuid.uuid4().hex[:12]}",
        "password": password,
    }

    try:
        with TestClient(app) as client:
            registration = client.post("/auth/register", json=register_payload)
            response = client.post(
                "/auth/login",
                json={"email": email, "password": password},
            )

        assert registration.status_code == 201
        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "bearer"

        payload = jwt.decode(
            body["access_token"],
            get_settings().jwt_secret_key,
            algorithms=[ALGORITHM],
        )
        assert payload["sub"] == registration.json()["id"]
    finally:
        asyncio.run(_delete_test_user(email))


def test_login_returns_401_for_unknown_email() -> None:
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/auth/login",
            json={
                "email": "unknown@example.com",
                "password": "correct horse battery staple",
            },
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_current_user_returns_user_for_valid_bearer_token() -> None:
    email = f"me-api-{uuid.uuid4()}@example.com"
    password = "correct horse battery staple"
    register_payload = {
        "email": email,
        "user_name": f"user_{uuid.uuid4().hex[:12]}",
        "password": password,
    }

    try:
        with TestClient(app) as client:
            registration = client.post("/auth/register", json=register_payload)
            login = client.post(
                "/auth/login",
                json={"email": email, "password": password},
            )
            response = client.get(
                "/auth/me",
                headers={"Authorization": f"Bearer {login.json()['access_token']}"},
            )

        assert registration.status_code == 201
        assert login.status_code == 200
        assert response.status_code == 200
        assert response.json()["id"] == registration.json()["id"]
        assert response.json()["email"] == email
        assert "password_hash" not in response.json()
    finally:
        asyncio.run(_delete_test_user(email))


def test_current_user_rejects_missing_and_invalid_tokens() -> None:
    with TestClient(app, raise_server_exceptions=False) as client:
        missing_token = client.get("/auth/me")
        invalid_token = client.get(
            "/auth/me",
            headers={"Authorization": "Bearer forged-token"},
        )

    assert missing_token.status_code == 401
    assert invalid_token.status_code == 401
    assert missing_token.json()["detail"] == "Could not validate credentials"
    assert invalid_token.json()["detail"] == "Could not validate credentials"
