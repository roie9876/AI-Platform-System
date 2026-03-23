from sqlalchemy import Column, String, Text, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.models.base import Base, UUIDMixin, TimestampMixin


class DataSource(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "data_sources"

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    source_type = Column(String(50), nullable=False)
    config = Column(JSONB, nullable=True)
    credentials_encrypted = Column(Text, nullable=True)
    status = Column(String(50), default="pending", nullable=False)
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )


class AgentDataSource(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "agent_data_sources"
    __table_args__ = (
        UniqueConstraint("agent_id", "data_source_id", name="uq_agent_data_source"),
    )

    agent_id = Column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    data_source_id = Column(
        UUID(as_uuid=True), ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False
    )
