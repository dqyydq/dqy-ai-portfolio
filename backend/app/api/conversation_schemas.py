from pydantic import BaseModel,Field,ConfigDict
from uuid import UUID
from datetime import datetime
from app.models.conversation import ConversationMode, MessageRole

class ConversationCreate(BaseModel):
    title:str=Field(...,min_length=1,max_length=255)
    mode: ConversationMode = ConversationMode.GENERAL
    learning_day: int | None = Field(default=None, ge=1, le=7)

    def model_post_init(self, __context) -> None:
        if self.mode is ConversationMode.PROJECT_INTERVIEW and self.learning_day is None:
            raise ValueError("learning_day is required for a project interview")
        if self.mode is ConversationMode.GENERAL and self.learning_day is not None:
            raise ValueError("learning_day is only available for a project interview")


class ConversationLearningContextUpdate(BaseModel):
    learning_day: int = Field(..., ge=1, le=7)



class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id:UUID
    user_id:UUID
    title:str
    mode: ConversationMode
    learning_day: int | None
    created_at:datetime


class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1)

class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    conversation_id: UUID
    role: MessageRole
    content: str
    created_at: datetime
