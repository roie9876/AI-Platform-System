from sqlalchemy import Column, String, Boolean, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base, UUIDMixin, TimestampMixin


class ModelEndpoint(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "model_endpoints"

    name = Column(String(255), nullable=False)
    provider_type = Column(String(50), nullable=False)  # azure_openai, openai, anthropic, custom
    endpoint_url = Column(String(1024), nullable=True)
    model_name = Column(String(255), nullable=False)
    api_key_encrypted = Column(String(2048), nullable=True)
    auth_type = Column(String(50), nullable=False)  # entra_id, api_key
    is_active = Column(Boolean, default=True, nullable=False)
    priority = Column(Integer, default=0, nullable=False)
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
