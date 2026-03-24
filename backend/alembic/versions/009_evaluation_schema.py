"""Add evaluation tables

Revision ID: 009
Revises: 008
Create Date: 2026-03-24 10:30:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "test_suites",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_test_suites_agent_tenant", "test_suites", ["agent_id", "tenant_id"])

    op.create_table(
        "test_cases",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("test_suite_id", UUID(as_uuid=True), sa.ForeignKey("test_suites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("input_message", sa.Text(), nullable=False),
        sa.Column("expected_output", sa.Text(), nullable=True),
        sa.Column("expected_keywords", JSONB, nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("order_index", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_test_cases_suite_id", "test_cases", ["test_suite_id"])

    op.create_table(
        "evaluation_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("test_suite_id", UUID(as_uuid=True), sa.ForeignKey("test_suites.id"), nullable=False),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("config_version_id", UUID(as_uuid=True), sa.ForeignKey("agent_config_versions.id"), nullable=True),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", JSONB, nullable=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_evaluation_runs_suite_status", "evaluation_runs", ["test_suite_id", "status"])

    op.create_table(
        "evaluation_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("test_case_id", UUID(as_uuid=True), sa.ForeignKey("test_cases.id"), nullable=False),
        sa.Column("actual_output", sa.Text(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("metrics", JSONB, nullable=True),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_evaluation_results_run_id", "evaluation_results", ["run_id"])


def downgrade() -> None:
    op.drop_table("evaluation_results")
    op.drop_table("evaluation_runs")
    op.drop_table("test_cases")
    op.drop_table("test_suites")
