from redis.exceptions import RedisError
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.db.database import session_factory
from app.realtime.publisher import build_user_realtime_channel
from app.realtime.websocket_auth import get_websocket_user


router = APIRouter(tags=["realtime"])


@router.websocket("/ws/events")
async def websocket_events(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token")

    async with session_factory() as session:
        user = await get_websocket_user(
            token=token,
            session=session,
        )

    if user is None:
        await websocket.close(code=4401)
        return

    await websocket.accept()

    redis_client = websocket.app.state.redis_client
    pubsub = redis_client.pubsub()

    try:
        await pubsub.subscribe(
            build_user_realtime_channel(user.id),
        )

        while True:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=1.0,
            )
            if message is not None:
                await websocket.send_text(message["data"])

    except WebSocketDisconnect:
        pass
    except RedisError:
        await websocket.close(code=1011)
    finally:
        await pubsub.unsubscribe()
        await pubsub.aclose()