from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID


class RealtimeEventType(str, Enum):
    MESSAGE_STARTED = "message.started"
    MESSAGE_DELTA = "message.delta"
    MESSAGE_COMPLETED = "message.completed"
    MESSAGE_FAILED = "message.failed"

    REVIEW_STATUS = "review.status"
    REVIEW_COMPLETED = "review.completed"
    REVIEW_FAILED = "review.failed"

    ERROR = "error"


@dataclass
class RealtimeEvent:
    type: RealtimeEventType
    data: dict[str, object] = field(default_factory=dict)
    conversation_id: UUID | None = None
    task_id: UUID | None = None
    version: int = 1
    occurred_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def to_payload(self) -> dict[str, object]:
        return {
            "version": self.version,
            "type": self.type.value,
            "conversation_id": (
                str(self.conversation_id)
                if self.conversation_id is not None
                else None
            ),
            "task_id": str(self.task_id) if self.task_id is not None else None,
            "data": self.data,
            "occurred_at": self.occurred_at.isoformat(),
        }