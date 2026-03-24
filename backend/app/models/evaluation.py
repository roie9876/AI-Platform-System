from sqlalchemy import Column, String, Integer, Float, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.models.base import Base, TimestampMixin, UUIDMixin


class TestSuite(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "test_suites"

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    agent_id = Column(
        UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False, index=True
    )
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    is_active = Column(Boolean, default=True, nullable=False)


class TestCase(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "test_cases"

    test_suite_id = Column(
        UUID(as_uuid=True),
        ForeignKey("test_suites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    input_message = Column(Text, nullable=False)
    expected_output = Column(Text, nullable=True)
    expected_keywords = Column(JSONB, nullable=True)
    metadata_ = Column("metadata", JSONB, nullable=True)
    order_index = Column(Integer, default=0, nullable=False)


class EvaluationRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "evaluation_runs"

    test_suite_id = Column(
        UUID(as_uuid=True), ForeignKey("test_suites.id"), nullable=False, index=True
    )
    agent_id = Column(
        UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False
    )
    config_version_id = Column(
        UUID(as_uuid=True), ForeignKey("agent_config_versions.id"), nullable=True
    )
    status = Column(String(20), default="pending", nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    summary = Column(JSONB, nullable=True)
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )


class EvaluationResult(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "evaluation_results"

    run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    test_case_id = Column(
        UUID(as_uuid=True), ForeignKey("test_cases.id"), nullable=False
    )
    actual_output = Column(Text, nullable=True)
    score = Column(Float, nullable=True)
    metrics = Column(JSONB, nullable=True)
    status = Column(String(20), default="pending", nullable=False)
    error_message = Column(Text, nullable=True)
