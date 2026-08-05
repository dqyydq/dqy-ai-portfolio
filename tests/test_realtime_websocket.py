import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from starlette.websockets import WebSocketDisconnect

from app.db.database import close_database, session_factory
from app.db.redis import create_redis_client
from app.main import app
from app.models.user import User
from app.realtime.events import RealtimeEvent, RealtimeEventType
from app.realtime.publisher import publish_user_realtime_event


def test_websocket_rejects_missing_token() -> None:
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as error:
            with client.websocket_connect("/ws/events"):
                pass

    assert error.value.code == 4401


async def _publish_event(user_id: uuid.UUID) -> None:
    redis_client = create_redis_client()
    try:
        await publish_user_realtime_event(
            redis_client=redis_client,
            user_id=user_id,
            event=RealtimeEvent(
                type=RealtimeEventType.REVIEW_STATUS,
                data={"status": "running"},
            ),
        )
    finally:
        await redis_client.aclose()


async def _delete_user(email: str) -> None:
    try:
        async with session_factory() as session:
            user = await session.scalar(select(User).where(User.email == email))
            if user is not None:
                await session.execute(delete(User).where(User.id == user.id))
                await session.commit()
    finally:
        await close_database()


def test_websocket_forwards_authenticated_user_event() -> None:
    email = f"realtime-ws-{uuid.uuid4()}@example.com"
    password = "correct horse battery staple"

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
            assert registration.status_code == 201
            assert login.status_code == 200

            with client.websocket_connect(
                f"/ws/events?token={login.json()['access_token']}",
            ) as websocket:
                asyncio.run(_publish_event(uuid.UUID(registration.json()["id"])))
                payload = websocket.receive_json()

        assert payload["type"] == "review.status"
        assert payload["data"] == {"status": "running"}
    finally:
        asyncio.run(_delete_user(email))
