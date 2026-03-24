from sqlalchemy import Column, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.base import Base, TimestampMixin, UUIDMixin


class ThreadMessage(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "thread_messages"
    __table_args__ = (
        UniqueConstraint("thread_id", "sequence_number", name="uq_thread_sequence"),
    )

    thread_id = Column(
        UUID(as_uuid=True),
        ForeignKey("threads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(20), nullable=False)  # user, assistant, system, tool
    content = Column(Text, nullable=False)
    message_metadata = Column(JSONB, nullable=True)  # tool_calls, sources, etc.
    sequence_number = Column(Integer, nullable=False)
