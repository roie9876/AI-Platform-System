from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.base import Base, TimestampMixin, UUIDMixin


class ExecutionLog(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "execution_logs"

    thread_id = Column(
        UUID(as_uuid=True),
        ForeignKey("threads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message_id = Column(
        UUID(as_uuid=True),
        ForeignKey("thread_messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_type = Column(String(50), nullable=False)  # message_sent, tool_call, model_response, error
    state_snapshot = Column(JSONB, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    token_count = Column(JSONB, nullable=True)  # {input_tokens, output_tokens}
