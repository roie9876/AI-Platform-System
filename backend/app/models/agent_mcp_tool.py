from sqlalchemy import Column, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base, UUIDMixin, TimestampMixin


class AgentMCPTool(Base, UUIDMixin, TimestampMixin):
    """Links an agent to a discovered MCP tool."""

    __tablename__ = "agent_mcp_tools"
    __table_args__ = (
        UniqueConstraint(
            "agent_id", "mcp_tool_id", name="uq_agent_mcp_tool"
        ),
    )

    agent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mcp_tool_id = Column(
        UUID(as_uuid=True),
        ForeignKey("mcp_discovered_tools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
