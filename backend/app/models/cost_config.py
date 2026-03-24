from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base, TimestampMixin, UUIDMixin


class ModelPricing(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "model_pricing"

    model_name = Column(String(255), nullable=False)
    provider_type = Column(String(50), nullable=False)
    input_price_per_1k = Column(Float, nullable=False)
    output_price_per_1k = Column(Float, nullable=False)
    currency = Column(String(10), default="USD", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True, index=True
    )


class CostAlert(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "cost_alerts"

    name = Column(String(255), nullable=False)
    alert_type = Column(String(50), nullable=False)  # budget_threshold, spike_detection
    threshold_amount = Column(Float, nullable=False)
    period = Column(String(20), nullable=False)  # daily, weekly, monthly
    scope_type = Column(String(50), nullable=False)  # agent, tenant, model
    scope_id = Column(UUID(as_uuid=True), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    last_triggered_at = Column(DateTime(timezone=True), nullable=True)
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
