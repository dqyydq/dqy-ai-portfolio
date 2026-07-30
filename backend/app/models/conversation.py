from datetime import datetime, timezone

from sqlalchemy import DateTime, String,ForeignKey,Enum
from sqlalchemy.orm import Mapped, mapped_column,relationship
import uuid
from datetime import datetime, timezone
from app.db.base import Base
from models.user import User
from typing import Text

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class Conversation(Base):
    __tablename__ = "conversations"
    id:Mapped[uuid.UUID]=mapped_column(primary_key=True,default=uuid.uuid4)
    user_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("users.id"),nullable=False)
    title:Mapped[str]=mapped_column(String(255),nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=lambda: datetime.now(timezone.utc),nullable=False)


class Message(Base):
    __tablename__ = "messages"
    id:Mapped[uuid.UUID]=mapped_column(primary_key=True,default=uuid.uuid4)
    conversation_id:Mapped[uuid.UUID]=mapped_column(ForeignKey("conversations.id"),nullable=False)
    role:Mapped[MessageRole]=mapped_column(Enum(MessageRole,name="message_role"),nullable=False)
    content:Mapped[Text]=mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=lambda: datetime.now(timezone.utc),nullable=False)


