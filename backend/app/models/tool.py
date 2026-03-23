from sqlalchemy import Column, String, Integer, Text, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.models.base import Base, UUIDMixin, TimestampMixin


class Tool(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "tools"

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    input_schema = Column(JSONB, nullable=False)
    output_schema = Column(JSONB, nullable=True)
    docker_image = Column(String(512), nullable=True)
    execution_command = Column(String(1024), nullable=True)
    timeout_seconds = Column(Integer, default=30, nullable=False)
    is_platform_tool = Column(Boolean, default=False, nullable=False)
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True, index=True
    )


class AgentTool(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "agent_tools"
    __table_args__ = (
        UniqueConstraint("agent_id", "tool_id", name="uq_agent_tool"),
    )

    agent_id = Column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    tool_id = Column(
        UUID(as_uuid=True), ForeignKey("tools.id", ondelete="CASCADE"), nullable=False
    )
