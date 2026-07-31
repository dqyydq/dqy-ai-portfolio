from pydantic import BaseModel,Field,ConfigDict
from uuid import UUID
from datetime import datetime
from app.models.conversation import MessageRole

class ConversationCreate(BaseModel):
    title:str=Field(...,min_length=1,max_length=255)



class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id:UUID
    user_id:UUID
    title:str
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