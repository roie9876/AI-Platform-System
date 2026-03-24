from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.models.base import Base, UUIDMixin, TimestampMixin


class AzureConnection(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "azure_connections"
    __table_args__ = (
        UniqueConstraint("agent_id", "resource_id", name="uq_agent_azure_connection"),
    )

    agent_id = Column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=True, index=True
    )
    azure_subscription_id = Column(
        UUID(as_uuid=True), ForeignKey("azure_subscriptions.id", ondelete="CASCADE"), nullable=False
    )
    resource_type = Column(String(255), nullable=False)
    resource_name = Column(String(255), nullable=False)
    resource_id = Column(String(1024), nullable=False)
    endpoint = Column(String(1024), nullable=True)
    region = Column(String(100), nullable=True)
    auth_type = Column(String(50), nullable=False, default="api_key")
    credentials_encrypted = Column(Text, nullable=True)
    health_status = Column(String(50), default="unknown", nullable=False)
    last_health_check = Column(DateTime(timezone=True), nullable=True)
    config = Column(JSONB, nullable=True)
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
