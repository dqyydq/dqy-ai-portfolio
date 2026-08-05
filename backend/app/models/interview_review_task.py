import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InterviewReviewStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class InterviewReviewTask(Base):
    __tablename__ = "interview_review_tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        nullable=False,
        index=True,
    )
    learning_day: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[InterviewReviewStatus] = mapped_column(
        SqlEnum(
            InterviewReviewStatus,
            name="interview_review_status",
            values_callable=lambda enum_cls: [
                member.value for member in enum_cls
            ],
        ),
        nullable=False,
        default=InterviewReviewStatus.QUEUED,
        index=True,
    )
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
