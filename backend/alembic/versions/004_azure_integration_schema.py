"""Azure integration schema - subscriptions, connections, catalog

Revision ID: 004
Revises: 003
Create Date: 2026-03-24
"""

from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "azure_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("subscription_id", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("tenant_azure_id", sa.String(255), nullable=False),
        sa.Column("state", sa.String(50), nullable=False, server_default=sa.text("'Enabled'")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("access_token_encrypted", sa.Text(), nullable=True),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("subscription_id", "tenant_id", name="uq_subscription_tenant"),
    )

    op.create_table(
        "azure_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("azure_subscription_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("azure_subscriptions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resource_type", sa.String(255), nullable=False),
        sa.Column("resource_name", sa.String(255), nullable=False),
        sa.Column("resource_id", sa.String(1024), nullable=False),
        sa.Column("endpoint", sa.String(1024), nullable=True),
        sa.Column("region", sa.String(100), nullable=True),
        sa.Column("auth_type", sa.String(50), nullable=False, server_default=sa.text("'api_key'")),
        sa.Column("credentials_encrypted", sa.Text(), nullable=True),
        sa.Column("health_status", sa.String(50), nullable=False, server_default=sa.text("'unknown'")),
        sa.Column("last_health_check", sa.DateTime(timezone=True), nullable=True),
        sa.Column("config", postgresql.JSONB(), nullable=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("agent_id", "resource_id", name="uq_agent_azure_connection"),
    )

    op.create_table(
        "catalog_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("connector_type", sa.String(100), nullable=False, unique=True),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False, server_default=sa.text("'Microsoft'")),
        sa.Column("icon_name", sa.String(100), nullable=True),
        sa.Column("badges", postgresql.JSONB(), nullable=True),
        sa.Column("config_schema", postgresql.JSONB(), nullable=True),
        sa.Column("auth_types", postgresql.JSONB(), nullable=True),
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("arm_resource_type", sa.String(255), nullable=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Seed builtin catalog entries
    catalog_entries_table = sa.table(
        "catalog_entries",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("connector_type", sa.String),
        sa.column("category", sa.String),
        sa.column("provider", sa.String),
        sa.column("icon_name", sa.String),
        sa.column("badges", postgresql.JSONB),
        sa.column("auth_types", postgresql.JSONB),
        sa.column("is_builtin", sa.Boolean),
        sa.column("arm_resource_type", sa.String),
    )

    op.bulk_insert(
        catalog_entries_table,
        [
            {
                "id": str(uuid.uuid4()),
                "name": "Azure AI Search",
                "description": "Connect to Azure AI Search for full-text and vector search over your data.",
                "connector_type": "azure_ai_search",
                "category": "AI Service",
                "provider": "Microsoft",
                "icon_name": "search",
                "badges": [],
                "auth_types": ["api_key", "managed_identity"],
                "is_builtin": True,
                "arm_resource_type": "Microsoft.Search/searchServices",
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Azure Cosmos DB",
                "description": "Connect to Azure Cosmos DB for NoSQL document storage and queries.",
                "connector_type": "azure_cosmos_db",
                "category": "Database",
                "provider": "Microsoft",
                "icon_name": "database",
                "badges": ["Preview"],
                "auth_types": ["connection_string", "managed_identity"],
                "is_builtin": True,
                "arm_resource_type": "Microsoft.DocumentDB/databaseAccounts",
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Azure PostgreSQL",
                "description": "Connect to Azure Database for PostgreSQL Flexible Server.",
                "connector_type": "azure_postgresql",
                "category": "Database",
                "provider": "Microsoft",
                "icon_name": "database",
                "badges": ["Preview"],
                "auth_types": ["connection_string", "managed_identity"],
                "is_builtin": True,
                "arm_resource_type": "Microsoft.DBforPostgreSQL/flexibleServers",
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("catalog_entries")
    op.drop_table("azure_connections")
    op.drop_table("azure_subscriptions")
