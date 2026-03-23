from sqlalchemy import Column, String, Boolean

from app.models.base import Base, UUIDMixin, TimestampMixin


class Tenant(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "tenants"

    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
