from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.conversation_schemas import (
    ConversationCreate,
    ConversationResponse,
)
from app.api.deps import get_current_user, get_llm_client
from app.db.database import get_session
from app.models.user import User

from uuid import UUID

from fastapi import HTTPException
from app.api.conversation_schemas import MessageCreate, MessageResponse
from app.services.conversation_service import (
    ConversationNotFoundError,
    create_conversation,
    get_conversation_for_user,
    list_conversations,
    list_messages,
    send_message_and_generate,
)
from app.clients.llm_client import LLMCallError, LLMClient, LLMResponseError



router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post(
    "/",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_new_conversation(
    data: ConversationCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ConversationResponse:
    return await create_conversation(
        session=session,
        user_id=current_user.id,
        data=data,
    )



@router.get(
    "/",
    response_model=list[ConversationResponse],
)
async def read_conversations(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ConversationResponse]:
    return await list_conversations(
        session=session,
        user_id=current_user.id,
    )


@router.get(
    "/{conversation_id}/messages",
    response_model=list[MessageResponse],
)
async def read_messages(
    conversation_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[MessageResponse]:
    conversation = await get_conversation_for_user(
        session=session,
        conversation_id=conversation_id,
        user_id=current_user.id,
    )

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    return await list_messages(
        session=session,
        conversation_id=conversation.id,
    )

@router.post(
    "/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_message(
    conversation_id: UUID,
    data: MessageCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    llm_client: Annotated[LLMClient, Depends(get_llm_client)],
) -> MessageResponse:
    try:
        return await send_message_and_generate(
            session=session,
            user_id=current_user.id,
            conversation_id=conversation_id,
            data=data,
            llm_client=llm_client,
        )
    except ConversationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    except (LLMCallError, LLMResponseError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM generation failed",
        )
