from datetime import datetime, timezone

from enum import Enum
from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
import uuid
from datetime import datetime, timezone
from app.db.base import Base


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class ConversationMode(str, Enum):
    GENERAL = "general"
    PROJECT_INTERVIEW = "project_interview"


class Conversation(Base):
    __tablename__ = "conversations"
    id:Mapped[uuid.UUID]=mapped_column(primary_key=True,default=uuid.uuid4)
    user_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("users.id"),nullable=False)
    title:Mapped[str]=mapped_column(String(255),nullable=False)
    mode: Mapped[ConversationMode] = mapped_column(
        SqlEnum(
            ConversationMode,
            name="conversation_mode",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=ConversationMode.GENERAL,
    )
    learning_day: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=lambda: datetime.now(timezone.utc),nullable=False)


class Message(Base):
    __tablename__ = "messages"
    id:Mapped[uuid.UUID]=mapped_column(primary_key=True,default=uuid.uuid4)
    conversation_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("conversations.id"),nullable=False)
    role: Mapped[MessageRole] = mapped_column(
    SqlEnum(
        MessageRole,
        name="message_role",
        values_callable=lambda enum_cls: [
            member.value for member in enum_cls
        ],
    ),
    nullable=False,
)
    content:Mapped[str]=mapped_column(Text,nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=lambda: datetime.now(timezone.utc),nullable=False)


