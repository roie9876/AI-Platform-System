from sqlalchemy import Column, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base, UUIDMixin, TimestampMixin


class AzureSubscription(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "azure_subscriptions"
    __table_args__ = (
        UniqueConstraint("subscription_id", "tenant_id", name="uq_subscription_tenant"),
    )

    subscription_id = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=False)
    tenant_azure_id = Column(String(255), nullable=False)
    state = Column(String(50), default="Enabled", nullable=False)
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    access_token_encrypted = Column(Text, nullable=True)
    refresh_token_encrypted = Column(Text, nullable=True)
    token_expires_at = Column(DateTime(timezone=True), nullable=True)
