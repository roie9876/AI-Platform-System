from sqlalchemy import Column, String, Integer, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.models.base import Base, UUIDMixin, TimestampMixin


class Document(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "documents"

    data_source_id = Column(
        UUID(as_uuid=True), ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename = Column(String(512), nullable=False)
    content_type = Column(String(100), nullable=True)
    file_size = Column(Integer, nullable=True)
    content_hash = Column(String(64), nullable=True)
    status = Column(String(50), default="pending", nullable=False)
    chunk_count = Column(Integer, default=0, nullable=False)
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )


class DocumentChunk(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "document_chunks"

    document_id = Column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    chunk_metadata = Column("metadata", JSONB, nullable=True)
    embedding = Column(JSONB, nullable=True)
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
