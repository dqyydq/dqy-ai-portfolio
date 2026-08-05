import asyncio
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.api.deps import get_llm_client
from app.db.database import close_database, session_factory
from app.main import app
from app.models.conversation import Conversation, Message
from app.models.user import User


class FakeStreamingLLMClient:
    async def stream_generate(self, _history, cache_scope: str):
        assert cache_scope.startswith("conversation:")
        for delta in ("Hello", " streaming"):
            yield delta


async def _cleanup_user(email: str) -> None:
    try:
        async with session_factory() as session:
            user = await session.scalar(select(User).where(User.email == email))
            if user is not None:
                conversation_ids = list(
                    (
                        await session.scalars(
                            select(Conversation.id).where(Conversation.user_id == user.id),
                        )
                    ).all(),
                )
                if conversation_ids:
                    await session.execute(
                        delete(Message).where(Message.conversation_id.in_(conversation_ids)),
                    )
                await session.execute(delete(Conversation).where(Conversation.user_id == user.id))
                await session.execute(delete(User).where(User.id == user.id))
                await session.commit()
    finally:
        await close_database()


def test_sse_streams_events_then_persists_full_assistant_message() -> None:
    email = f"sse-{uuid.uuid4()}@example.com"
    password = "correct horse battery staple"
    app.dependency_overrides[get_llm_client] = lambda: FakeStreamingLLMClient()

    try:
        with TestClient(app) as client:
            registration = client.post(
                "/auth/register",
                json={
                    "email": email,
                    "user_name": f"user_{uuid.uuid4().hex[:12]}",
                    "password": password,
                },
            )
            login = client.post(
                "/auth/login",
                json={"email": email, "password": password},
            )
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            conversation = client.post(
                "/conversations/",
                json={"title": "SSE test"},
                headers=headers,
            )

            with client.stream(
                "POST",
                f"/conversations/{conversation.json()['id']}/messages/stream",
                json={"content": "Stream this"},
                headers=headers,
            ) as response:
                body = "".join(response.iter_text())

            messages = client.get(
                f"/conversations/{conversation.json()['id']}/messages",
                headers=headers,
            )

        assert registration.status_code == 201
        assert login.status_code == 200
        assert conversation.status_code == 201
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert [line for line in body.splitlines() if line.startswith("event:")] == [
            "event: message.started",
            "event: message.delta",
            "event: message.delta",
            "event: message.completed",
        ]
        assert [message["content"] for message in messages.json()] == [
            "Stream this",
            "Hello streaming",
        ]
    finally:
        app.dependency_overrides.pop(get_llm_client, None)
        asyncio.run(_cleanup_user(email))
