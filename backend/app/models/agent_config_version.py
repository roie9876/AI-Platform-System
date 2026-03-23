from sqlalchemy import Column, String, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSON

from app.models.base import Base, UUIDMixin, TimestampMixin


class AgentConfigVersion(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "agent_config_versions"

    agent_id = Column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number = Column(Integer, nullable=False)
    config_snapshot = Column(JSON, nullable=False)
    change_description = Column(String(500), nullable=True)
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )

    __table_args__ = (
        UniqueConstraint("agent_id", "version_number", name="uq_agent_config_version"),
    )
