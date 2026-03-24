"""Make azure_connections.agent_id optional for platform-level connections

Revision ID: 005
Revises: 004
Create Date: 2025-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "azure_connections",
        "agent_id",
        existing_type=sa.UUID(),
        nullable=True,
    )
    op.drop_constraint("uq_agent_azure_connection", "azure_connections", type_="unique")
    op.create_unique_constraint(
        "uq_agent_azure_connection",
        "azure_connections",
        ["agent_id", "resource_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_agent_azure_connection", "azure_connections", type_="unique")
    op.create_unique_constraint(
        "uq_agent_azure_connection",
        "azure_connections",
        ["agent_id", "resource_id"],
    )
    op.alter_column(
        "azure_connections",
        "agent_id",
        existing_type=sa.UUID(),
        nullable=False,
    )
