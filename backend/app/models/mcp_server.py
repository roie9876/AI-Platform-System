from sqlalchemy import Column, String, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base, UUIDMixin, TimestampMixin


class MCPServer(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "mcp_servers"

    name = Column(String(255), nullable=False)
    url = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    auth_type = Column(
        String(50), nullable=False, default="none"
    )  # none, bearer, api_key, custom_header
    auth_header_name = Column(String(255), nullable=True)  # Custom header name for auth
    auth_credential_ref = Column(
        Text, nullable=True
    )  # Reference to secret store (never raw credentials)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    status = Column(
        String(50), nullable=False, default="unknown"
    )  # unknown, connected, error, unreachable
    status_message = Column(Text, nullable=True)
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
