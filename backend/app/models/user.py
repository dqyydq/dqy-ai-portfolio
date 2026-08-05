# backend/app/models/user.py
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

class User(Base):
    __tablename__ = "users"

    # 依次补齐 5 个字段
    id:Mapped[uuid.UUID]=mapped_column(primary_key=True, default=uuid.uuid4)
    email:Mapped[str]=mapped_column(String(255), unique=True, nullable=False,index=True)
    user_name:Mapped[str]=mapped_column(String(50),nullable=False,unique=True,index=True)
    password_hash:Mapped[str] = mapped_column(String(255), nullable=False)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deepseek_api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    deepseek_api_key_hint: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=lambda: datetime.now(timezone.utc),nullable=False)

