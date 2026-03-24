from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.base import Base, TimestampMixin, UUIDMixin


class Workflow(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "workflows"

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    is_active = Column(Boolean, default=True, nullable=False)
    workflow_type = Column(String(50), default="sequential", nullable=False)
    metadata_ = Column("metadata", JSONB, nullable=True)


class WorkflowNode(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "workflow_nodes"

    workflow_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agents.id"),
        nullable=False,
    )
    name = Column(String(255), nullable=False)
    node_type = Column(String(50), default="agent", nullable=False)
    position_x = Column(Float, default=0, nullable=False)
    position_y = Column(Float, default=0, nullable=False)
    config = Column(JSONB, nullable=True)
    execution_order = Column(Integer, default=0, nullable=False)


class WorkflowEdge(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "workflow_edges"

    workflow_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_node_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflow_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_node_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflow_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    edge_type = Column(String(50), default="default", nullable=False)
    condition = Column(JSONB, nullable=True)
    output_mapping = Column(JSONB, nullable=True)
