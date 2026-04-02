from sqlalchemy import Column, String, Integer, Float, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base, UUIDMixin, TimestampMixin


class Agent(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "agents"

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    system_prompt = Column(Text, nullable=True)
    status = Column(String(50), default="inactive", nullable=False)
    temperature = Column(Float, default=0, nullable=False)
    max_tokens = Column(Integer, default=128000, nullable=False)
    timeout_seconds = Column(Integer, default=30, nullable=False)
    current_config_version = Column(Integer, default=1, nullable=False)
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    model_endpoint_id = Column(
        UUID(as_uuid=True), ForeignKey("model_endpoints.id"), nullable=True, index=True
    )
