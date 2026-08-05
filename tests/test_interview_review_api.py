import asyncio
import uuid

from fastapi.testclient import TestClient
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import delete, select

from app.api.deps import get_redis_client
from app.db.database import close_database, session_factory
from app.db.redis import create_redis_client
from app.main import app
from app.models.conversation import Conversation, Message
from app.models.interview_review_task import InterviewReviewTask
from app.models.user import User
from app.services.interview_review_queue_service import INTERVIEW_REVIEW_STREAM


class UnavailableRedis:
    async def xadd(self, *_args, **_kwargs):
        raise RedisConnectionError("Redis is unavailable")


async def _cleanup_user(email: str) -> None:
    try:
        async with session_factory() as session:
            user = await session.scalar(select(User).where(User.email == email))
            if user is None:
                return

            conversation_ids = list(
                (
                    await session.scalars(
                        select(Conversation.id).where(Conversation.user_id == user.id),
                    )
                ).all(),
            )
            await session.execute(
                delete(InterviewReviewTask).where(InterviewReviewTask.user_id == user.id),
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


async def _delete_stream_entry_for_task(task_id: str) -> None:
    redis_client: Redis = create_redis_client()
    try:
        entries = await redis_client.xrevrange(INTERVIEW_REVIEW_STREAM, count=100)
        for entry_id, fields in entries:
            if fields.get("task_id") == task_id:
                await redis_client.xdel(INTERVIEW_REVIEW_STREAM, entry_id)
                return
    finally:
        await redis_client.aclose()


def _register_and_login(client: TestClient, email: str) -> str:
    password = "correct horse battery staple"
    registration = client.post(
        "/auth/register",
        json={
            "email": email,
            "user_name": f"user_{uuid.uuid4().hex[:12]}",
            "password": password,
        },
    )
    assert registration.status_code == 201
    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    return login.json()["access_token"]


def test_interview_review_owner_can_enqueue_and_read_task() -> None:
    owner_email = f"review-owner-{uuid.uuid4()}@example.com"
    other_email = f"review-other-{uuid.uuid4()}@example.com"
    task_id: str | None = None

    try:
        with TestClient(app) as client:
            owner_token = _register_and_login(client, owner_email)
            other_token = _register_and_login(client, other_email)
            owner_headers = {"Authorization": f"Bearer {owner_token}"}
            other_headers = {"Authorization": f"Bearer {other_token}"}

            conversation = client.post(
                "/conversations/",
                json={
                    "title": "Redis Streams interview review",
                    "mode": "project_interview",
                    "learning_day": 6,
                },
                headers=owner_headers,
            )
            assert conversation.status_code == 201

            created = client.post(
                f"/interview-reviews/conversations/{conversation.json()['id']}",
                json={"session_id": str(uuid.uuid4())},
                headers=owner_headers,
            )

            assert created.status_code == 202
            task_id = created.json()["id"]
            assert created.json()["status"] == "queued"

            owner_read = client.get(f"/interview-reviews/{task_id}", headers=owner_headers)
            other_read = client.get(f"/interview-reviews/{task_id}", headers=other_headers)

        assert owner_read.status_code == 200
        assert owner_read.json()["id"] == task_id
        assert other_read.status_code == 404
    finally:
        if task_id is not None:
            asyncio.run(_delete_stream_entry_for_task(task_id))
        asyncio.run(_cleanup_user(owner_email))
        asyncio.run(_cleanup_user(other_email))


def test_interview_review_dispatch_failure_keeps_task_queryable() -> None:
    email = f"review-dispatch-{uuid.uuid4()}@example.com"
    task_id: str | None = None
    app.dependency_overrides[get_redis_client] = lambda: UnavailableRedis()

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            token = _register_and_login(client, email)
            headers = {"Authorization": f"Bearer {token}"}
            conversation = client.post(
                "/conversations/",
                json={
                    "title": "Dispatch failure",
                    "mode": "project_interview",
                    "learning_day": 6,
                },
                headers=headers,
            )
            assert conversation.status_code == 201

            response = client.post(
                f"/interview-reviews/conversations/{conversation.json()['id']}",
                json={"session_id": str(uuid.uuid4())},
                headers=headers,
            )

            assert response.status_code == 503
            task_id = response.json()["detail"]["task_id"]
            read_response = client.get(f"/interview-reviews/{task_id}", headers=headers)

        assert read_response.status_code == 200
        assert read_response.json()["status"] == "queued"
    finally:
        app.dependency_overrides.pop(get_redis_client, None)
        asyncio.run(_cleanup_user(email))
