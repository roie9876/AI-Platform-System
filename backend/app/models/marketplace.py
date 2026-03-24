from sqlalchemy import Column, String, Integer, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.models.base import Base, TimestampMixin, UUIDMixin


class AgentTemplate(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "agent_templates"

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)
    tags = Column(JSONB, nullable=True)
    system_prompt = Column(Text, nullable=True)
    config = Column(JSONB, nullable=True)
    tools_config = Column(JSONB, nullable=True)
    icon_name = Column(String(100), nullable=True)
    author_name = Column(String(255), nullable=True)
    author_tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True
    )
    is_public = Column(Boolean, default=True, nullable=False)
    is_featured = Column(Boolean, default=False, nullable=False)
    install_count = Column(Integer, default=0, nullable=False)
    version = Column(String(20), default="1.0", nullable=False)


class ToolTemplate(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "tool_templates"

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)
    tags = Column(JSONB, nullable=True)
    input_schema = Column(JSONB, nullable=True)
    tool_type = Column(String(50), nullable=False)
    config = Column(JSONB, nullable=True)
    author_name = Column(String(255), nullable=True)
    author_tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True
    )
    is_public = Column(Boolean, default=True, nullable=False)
    is_featured = Column(Boolean, default=False, nullable=False)
    install_count = Column(Integer, default=0, nullable=False)
    version = Column(String(20), default="1.0", nullable=False)
