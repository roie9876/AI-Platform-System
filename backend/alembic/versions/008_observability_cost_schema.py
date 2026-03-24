"""Add observability and cost tracking tables

Revision ID: 008
Revises: 007
Create Date: 2026-03-24 10:00:00.000000
"""
import uuid
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_pricing",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("model_name", sa.String(255), nullable=False),
        sa.Column("provider_type", sa.String(50), nullable=False),
        sa.Column("input_price_per_1k", sa.Float(), nullable=False),
        sa.Column("output_price_per_1k", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(10), server_default="USD", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_model_pricing_model_tenant", "model_pricing", ["model_name", "tenant_id"])

    op.create_table(
        "cost_alerts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("threshold_amount", sa.Float(), nullable=False),
        sa.Column("period", sa.String(20), nullable=False),
        sa.Column("scope_type", sa.String(50), nullable=False),
        sa.Column("scope_id", UUID(as_uuid=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_cost_alerts_tenant_scope", "cost_alerts", ["tenant_id", "scope_type"])

    # Seed default pricing for common models
    pricing_table = sa.table(
        "model_pricing",
        sa.column("id", UUID(as_uuid=True)),
        sa.column("model_name", sa.String),
        sa.column("provider_type", sa.String),
        sa.column("input_price_per_1k", sa.Float),
        sa.column("output_price_per_1k", sa.Float),
        sa.column("currency", sa.String),
        sa.column("is_active", sa.Boolean),
        sa.column("tenant_id", UUID(as_uuid=True)),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    op.bulk_insert(pricing_table, [
        {
            "id": uuid.uuid4(), "model_name": "gpt-4.1", "provider_type": "openai",
            "input_price_per_1k": 0.002, "output_price_per_1k": 0.008,
            "currency": "USD", "is_active": True, "tenant_id": None,
            "created_at": now, "updated_at": now,
        },
        {
            "id": uuid.uuid4(), "model_name": "gpt-4o", "provider_type": "openai",
            "input_price_per_1k": 0.0025, "output_price_per_1k": 0.01,
            "currency": "USD", "is_active": True, "tenant_id": None,
            "created_at": now, "updated_at": now,
        },
        {
            "id": uuid.uuid4(), "model_name": "gpt-4o-mini", "provider_type": "openai",
            "input_price_per_1k": 0.00015, "output_price_per_1k": 0.0006,
            "currency": "USD", "is_active": True, "tenant_id": None,
            "created_at": now, "updated_at": now,
        },
        {
            "id": uuid.uuid4(), "model_name": "gpt-3.5-turbo", "provider_type": "openai",
            "input_price_per_1k": 0.0005, "output_price_per_1k": 0.0015,
            "currency": "USD", "is_active": True, "tenant_id": None,
            "created_at": now, "updated_at": now,
        },
    ])


def downgrade() -> None:
    op.drop_table("cost_alerts")
    op.drop_table("model_pricing")
