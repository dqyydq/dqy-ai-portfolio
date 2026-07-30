# backend/app/models/user.py
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column,relationship

from app.db.base import Base
from models.conversation import Conversation

class User(Base):
    __tablename__ = "users"

    # 依次补齐 5 个字段
    id:Mapped[uuid.UUID]=mapped_column(primary_key=True, default=uuid.uuid4)
    email:Mapped[str]=mapped_column(String(255), unique=True, nullable=False,index=True)
    user_name:Mapped[str]=mapped_column(String(50),nullable=False,unique=True,index=True)
    password_hash:Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=lambda: datetime.now(timezone.utc),nullable=False)

