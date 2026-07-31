from app.models.conversation import Conversation,Message
from app.core.security import get_password_hash,verify_password
from app.api.conversation_schemas import ConversationCreate,ConversationResponse
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from sqlalchemy import select
from app.api.conversation_schemas import MessageCreate
from app.models.conversation import MessageRole



class ConversationNotFoundError(Exception):
    pass

async def create_conversation(
    session: AsyncSession,
    user_id: UUID,
    data: ConversationCreate,
) -> Conversation:
    conversation=Conversation(user_id=user_id,
                              title=data.title)

    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return conversation


async def list_conversations(
    session: AsyncSession,
    user_id: UUID,
) -> list[Conversation]:
    result = await session.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.created_at.desc()),
    )
    return list(result.scalars().all())



async def get_conversation_for_user(
    session: AsyncSession,
    conversation_id: UUID,
    user_id: UUID,
) -> Conversation | None:
    result=await session.execute(
        select(Conversation).where(
    Conversation.id == conversation_id,
    Conversation.user_id == user_id,
    )
)
    return result.scalar_one_or_none()



async def create_user_message(
    session: AsyncSession,
    conversation_id: UUID,
    data: MessageCreate,
) -> Message:
    message=Message(
        conversation_id=conversation_id,
        role=MessageRole.USER,
        content=data.content
    )

    session.add(message)
    await session.commit()
    await session.refresh(message)

    return message



async def create_assistant_message(
    session: AsyncSession,
    conversation_id: UUID,
    content: str,
) -> Message:
    message=Message(
    conversation_id=conversation_id,
    role=MessageRole.ASSISTANT,
    content=content
)

    session.add(message)
    await session.commit()
    await session.refresh(message)

    return message


async def list_messages(
    session: AsyncSession,
    conversation_id: UUID,
) -> list[Message]:
    result=await session.execute(
        select(Message)
        .where(Message.conversation_id==conversation_id)
        .order_by(Message.created_at.asc()),
    )
    return list(result.scalars().all())




def build_llm_history(messages: list[Message]) -> list[dict]:

    history=[]

    for message in messages:
        content_type=(
            "input_text"
            if message.role==MessageRole.USER else
            "output_text"
        )
        history.append(
            {
                "role":message.role.value,
                "content":[
                    {
                        "type":content_type,
                        "text":message.content
                    }
                ],
            }
        )
    return history


async def send_message_and_generate(
    session: AsyncSession,
    user_id: UUID,
    conversation_id: UUID,
    data: MessageCreate,
    llm_client,
) -> Message:
    conversation=await get_conversation_for_user(session,conversation_id,user_id)
    if conversation is None:
        raise ConversationNotFoundError("Conversation not found")

    await create_user_message(
        session=session,
        conversation_id=conversation_id,
        data=data
    )

    messages = await list_messages(
    session=session,
    conversation_id=conversation_id,
    )

    history = build_llm_history(messages)
    assistant_content = await llm_client.generate(history)

    return await create_assistant_message(
    session=session,
    conversation_id=conversation_id,
    content=assistant_content,
)
