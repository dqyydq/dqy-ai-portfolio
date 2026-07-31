import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.api.deps import get_llm_client
from app.clients.llm_client import LLMCallError
from app.db.database import close_database, session_factory
from app.main import app
from app.models.conversation import Conversation, Message
from app.models.user import User


class FakeLLMClient:
    def __init__(self, answer: str = "Mock assistant reply") -> None:
        self.answer = answer
        self.histories = []

    async def generate(self, history):
        self.histories.append(history)
        return self.answer


class FailingLLMClient:
    async def generate(self, history):
        raise LLMCallError("LLM request failed")


@pytest.fixture(autouse=True)
def fake_llm_dependency():
    app.dependency_overrides[get_llm_client] = lambda: FakeLLMClient()
    yield
    app.dependency_overrides.pop(get_llm_client, None)


async def _delete_test_data(email: str) -> None:
    try:
        async with session_factory() as session:
            user_result = await session.execute(
                select(User).where(User.email == email),
            )
            user = user_result.scalar_one_or_none()
            if user is not None:
                conversation_ids = list(
                    (
                        await session.scalars(
                            select(Conversation.id).where(
                                Conversation.user_id == user.id,
                            ),
                        )
                    ).all(),
                )
                if conversation_ids:
                    await session.execute(
                        delete(Message).where(
                            Message.conversation_id.in_(conversation_ids),
                        ),
                    )
                await session.execute(
                    delete(Conversation).where(Conversation.user_id == user.id),
                )
                await session.execute(delete(User).where(User.id == user.id))
                await session.commit()
    finally:
        await close_database()


def test_create_conversation_for_current_user() -> None:
    email = f"conversation-api-{uuid.uuid4()}@example.com"
    register_payload = {
        "email": email,
        "user_name": f"user_{uuid.uuid4().hex[:12]}",
        "password": "correct horse battery staple",
    }

    try:
        with TestClient(app) as client:
            registration = client.post("/auth/register", json=register_payload)
            login = client.post(
                "/auth/login",
                json={"email": email, "password": register_payload["password"]},
            )
            response = client.post(
                "/conversations/",
                json={"title": "Day 3 learning"},
                headers={"Authorization": f"Bearer {login.json()['access_token']}"},
            )

        assert registration.status_code == 201
        assert login.status_code == 200
        assert response.status_code == 201
        assert response.json()["title"] == "Day 3 learning"
        assert response.json()["user_id"] == registration.json()["id"]
    finally:
        asyncio.run(_delete_test_data(email))


def test_create_conversation_requires_token() -> None:
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/conversations/", json={"title": "No token"})

    assert response.status_code == 401


def test_conversation_list_is_isolated_by_current_user() -> None:
    first_email = f"first-{uuid.uuid4()}@example.com"
    second_email = f"second-{uuid.uuid4()}@example.com"
    password = "correct horse battery staple"
    first_payload = {
        "email": first_email,
        "user_name": f"first_{uuid.uuid4().hex[:12]}",
        "password": password,
    }
    second_payload = {
        "email": second_email,
        "user_name": f"second_{uuid.uuid4().hex[:12]}",
        "password": password,
    }

    try:
        with TestClient(app) as client:
            assert client.post("/auth/register", json=first_payload).status_code == 201
            assert client.post("/auth/register", json=second_payload).status_code == 201

            first_token = client.post(
                "/auth/login",
                json={"email": first_email, "password": password},
            ).json()["access_token"]
            second_token = client.post(
                "/auth/login",
                json={"email": second_email, "password": password},
            ).json()["access_token"]

            first_headers = {"Authorization": f"Bearer {first_token}"}
            second_headers = {"Authorization": f"Bearer {second_token}"}
            assert client.post(
                "/conversations/",
                json={"title": "First user's conversation"},
                headers=first_headers,
            ).status_code == 201
            assert client.post(
                "/conversations/",
                json={"title": "Second user's conversation"},
                headers=second_headers,
            ).status_code == 201

            first_list = client.get("/conversations/", headers=first_headers)
            second_list = client.get("/conversations/", headers=second_headers)

        assert first_list.status_code == 200
        assert second_list.status_code == 200
        assert [item["title"] for item in first_list.json()] == [
            "First user's conversation",
        ]
        assert [item["title"] for item in second_list.json()] == [
            "Second user's conversation",
        ]
    finally:
        asyncio.run(_delete_test_data(first_email))
        asyncio.run(_delete_test_data(second_email))


def test_message_creation_enforces_conversation_ownership_and_user_role() -> None:
    owner_email = f"message-owner-{uuid.uuid4()}@example.com"
    other_email = f"message-other-{uuid.uuid4()}@example.com"
    password = "correct horse battery staple"
    owner_payload = {
        "email": owner_email,
        "user_name": f"owner_{uuid.uuid4().hex[:12]}",
        "password": password,
    }
    other_payload = {
        "email": other_email,
        "user_name": f"other_{uuid.uuid4().hex[:12]}",
        "password": password,
    }

    try:
        with TestClient(app) as client:
            assert client.post("/auth/register", json=owner_payload).status_code == 201
            assert client.post("/auth/register", json=other_payload).status_code == 201
            owner_token = client.post(
                "/auth/login",
                json={"email": owner_email, "password": password},
            ).json()["access_token"]
            other_token = client.post(
                "/auth/login",
                json={"email": other_email, "password": password},
            ).json()["access_token"]
            owner_headers = {"Authorization": f"Bearer {owner_token}"}
            other_headers = {"Authorization": f"Bearer {other_token}"}
            conversation = client.post(
                "/conversations/",
                json={"title": "Private message thread"},
                headers=owner_headers,
            )
            conversation_id = conversation.json()["id"]

            owner_message = client.post(
                f"/conversations/{conversation_id}/messages",
                json={"content": "Hello", "role": "assistant"},
                headers=owner_headers,
            )
            second_owner_message = client.post(
                f"/conversations/{conversation_id}/messages",
                json={"content": "How are you?"},
                headers=owner_headers,
            )
            other_user_message = client.post(
                f"/conversations/{conversation_id}/messages",
                json={"content": "Forbidden"},
                headers=other_headers,
            )
            owner_history = client.get(
                f"/conversations/{conversation_id}/messages",
                headers=owner_headers,
            )
            other_user_history = client.get(
                f"/conversations/{conversation_id}/messages",
                headers=other_headers,
            )

        assert conversation.status_code == 201
        assert owner_message.status_code == 201
        assert owner_message.json()["content"] == "Mock assistant reply"
        assert owner_message.json()["role"] == "assistant"
        assert second_owner_message.status_code == 201
        assert other_user_message.status_code == 404
        assert other_user_message.json()["detail"] == "Conversation not found"
        assert owner_history.status_code == 200
        assert [message["content"] for message in owner_history.json()] == [
            "Hello",
            "Mock assistant reply",
            "How are you?",
            "Mock assistant reply",
        ]
        assert other_user_history.status_code == 404
    finally:
        asyncio.run(_delete_test_data(owner_email))
        asyncio.run(_delete_test_data(other_email))


def test_message_generation_failure_returns_502_and_keeps_user_message() -> None:
    email = f"llm-failure-{uuid.uuid4()}@example.com"
    password = "correct horse battery staple"
    payload = {
        "email": email,
        "user_name": f"user_{uuid.uuid4().hex[:12]}",
        "password": password,
    }
    app.dependency_overrides[get_llm_client] = lambda: FailingLLMClient()

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            assert client.post("/auth/register", json=payload).status_code == 201
            token = client.post(
                "/auth/login",
                json={"email": email, "password": password},
            ).json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            conversation = client.post(
                "/conversations/",
                json={"title": "Failure route test"},
                headers=headers,
            )
            conversation_id = conversation.json()["id"]

            response = client.post(
                f"/conversations/{conversation_id}/messages",
                json={"content": "Keep this input"},
                headers=headers,
            )
            history = client.get(
                f"/conversations/{conversation_id}/messages",
                headers=headers,
            )

        assert response.status_code == 502
        assert response.json()["detail"] == "LLM generation failed"
        assert [message["content"] for message in history.json()] == ["Keep this input"]
    finally:
        app.dependency_overrides.pop(get_llm_client, None)
        asyncio.run(_delete_test_data(email))
