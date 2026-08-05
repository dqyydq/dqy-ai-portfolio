from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class InterviewReviewCreate(BaseModel):
    pass


class InterviewReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversation_id: UUID
    session_id: UUID
    learning_day: int
    status: str
    result: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
