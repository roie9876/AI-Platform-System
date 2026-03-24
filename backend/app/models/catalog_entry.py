from sqlalchemy import Column, String, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.models.base import Base, UUIDMixin, TimestampMixin


class CatalogEntry(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "catalog_entries"

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    connector_type = Column(String(100), nullable=False, unique=True)
    category = Column(String(100), nullable=False)
    provider = Column(String(100), nullable=False, default="Microsoft")
    icon_name = Column(String(100), nullable=True)
    badges = Column(JSONB, nullable=True)
    config_schema = Column(JSONB, nullable=True)
    auth_types = Column(JSONB, nullable=True)
    is_builtin = Column(Boolean, default=True, nullable=False)
    arm_resource_type = Column(String(255), nullable=True)
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True, index=True
    )
