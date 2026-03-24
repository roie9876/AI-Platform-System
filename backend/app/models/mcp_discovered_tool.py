from sqlalchemy import Column, String, Text, Boolean, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base, UUIDMixin, TimestampMixin


class MCPDiscoveredTool(Base, UUIDMixin, TimestampMixin):
    """Tool discovered from a registered MCP server via tools/list."""

    __tablename__ = "mcp_discovered_tools"

    server_id = Column(
        UUID(as_uuid=True),
        ForeignKey("mcp_servers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tool_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    input_schema = Column(JSON, nullable=True)
    is_available = Column(Boolean, nullable=False, default=True, server_default="true")
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
