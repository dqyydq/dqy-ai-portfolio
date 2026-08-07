import json
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.conversation_schemas import ConversationCreate, ConversationResponse, MessageCreate, MessageResponse
from app.api.deps import get_current_user, get_llm_client, get_redis_client
from app.api.rate_limit import enforce_message_rate_limit
from app.clients.llm_client import LLMCallError, LLMClient, LLMResponseError
from app.db.database import get_session
from app.models.user import User
from app.services.conversation_service import ConversationNotFoundError, create_conversation, delete_conversation, get_conversation_for_user, list_conversations, list_messages, send_message_and_generate, stream_message_generation
from app.services.rate_limit_service import RateLimitResult

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("/", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_new_conversation(data: ConversationCreate, current_user: Annotated[User, Depends(get_current_user)], session: Annotated[AsyncSession, Depends(get_session)]) -> ConversationResponse:
    return await create_conversation(session=session, user_id=current_user.id, data=data)


@router.get("/", response_model=list[ConversationResponse])
async def read_conversations(current_user: Annotated[User, Depends(get_current_user)], session: Annotated[AsyncSession, Depends(get_session)]) -> list[ConversationResponse]:
    return await list_conversations(session=session, user_id=current_user.id)


@router.get("/{conversation_id}/messages", response_model=list[MessageResponse])
async def read_messages(conversation_id: UUID, current_user: Annotated[User, Depends(get_current_user)], session: Annotated[AsyncSession, Depends(get_session)]) -> list[MessageResponse]:
    conversation = await get_conversation_for_user(session, conversation_id, current_user.id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return await list_messages(session, conversation.id)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_conversation(
    conversation_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    deleted = await delete_conversation(session, conversation_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")


@router.post("/{conversation_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def create_message(conversation_id: UUID, data: MessageCreate, current_user: Annotated[User, Depends(get_current_user)], session: Annotated[AsyncSession, Depends(get_session)], llm_client: Annotated[LLMClient, Depends(get_llm_client)], redis_client: Annotated[Redis, Depends(get_redis_client)], rate_limit: Annotated[RateLimitResult, Depends(enforce_message_rate_limit)]) -> MessageResponse:
    try:
        return await send_message_and_generate(session, current_user.id, conversation_id, data, llm_client, redis_client)
    except ConversationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    except (LLMCallError, LLMResponseError):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="LLM generation failed")


@router.post("/{conversation_id}/messages/stream")
async def stream_message(
    conversation_id: UUID,
    data: MessageCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    llm_client: Annotated[LLMClient, Depends(get_llm_client)],
    redis_client: Annotated[Redis, Depends(get_redis_client)],
    rate_limit: Annotated[RateLimitResult, Depends(enforce_message_rate_limit)],
) -> StreamingResponse:
    conversation = await get_conversation_for_user(session, conversation_id, current_user.id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    async def event_stream() -> AsyncIterator[str]:
        async for event in stream_message_generation(
            session=session,
            user_id=current_user.id,
            conversation_id=conversation_id,
            data=data,
            llm_client=llm_client,
            redis_client=redis_client,
        ):
            yield f"event: {event['type']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
