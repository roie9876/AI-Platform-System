"""Add marketplace tables

Revision ID: 010
Revises: 009
Create Date: 2026-03-24 11:00:00.000000
"""
import uuid
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("tags", JSONB, nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("config", JSONB, nullable=True),
        sa.Column("tools_config", JSONB, nullable=True),
        sa.Column("icon_name", sa.String(100), nullable=True),
        sa.Column("author_name", sa.String(255), nullable=True),
        sa.Column("author_tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("is_public", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_featured", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("install_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("version", sa.String(20), server_default="1.0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agent_templates_category", "agent_templates", ["category"])
    op.create_index("ix_agent_templates_public_featured", "agent_templates", ["is_public", "is_featured"])

    op.create_table(
        "tool_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("tags", JSONB, nullable=True),
        sa.Column("input_schema", JSONB, nullable=True),
        sa.Column("tool_type", sa.String(50), nullable=False),
        sa.Column("config", JSONB, nullable=True),
        sa.Column("author_name", sa.String(255), nullable=True),
        sa.Column("author_tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("is_public", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_featured", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("install_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("version", sa.String(20), server_default="1.0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_tool_templates_category", "tool_templates", ["category"])
    op.create_index("ix_tool_templates_public_featured", "tool_templates", ["is_public", "is_featured"])

    # Seed sample agent templates
    agent_table = sa.table(
        "agent_templates",
        sa.column("id", UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("category", sa.String),
        sa.column("tags", JSONB),
        sa.column("system_prompt", sa.Text),
        sa.column("config", JSONB),
        sa.column("tools_config", JSONB),
        sa.column("icon_name", sa.String),
        sa.column("author_name", sa.String),
        sa.column("author_tenant_id", UUID(as_uuid=True)),
        sa.column("is_public", sa.Boolean),
        sa.column("is_featured", sa.Boolean),
        sa.column("install_count", sa.Integer),
        sa.column("version", sa.String),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )

    tool_table = sa.table(
        "tool_templates",
        sa.column("id", UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("category", sa.String),
        sa.column("tags", JSONB),
        sa.column("input_schema", JSONB),
        sa.column("tool_type", sa.String),
        sa.column("config", JSONB),
        sa.column("author_name", sa.String),
        sa.column("author_tenant_id", UUID(as_uuid=True)),
        sa.column("is_public", sa.Boolean),
        sa.column("is_featured", sa.Boolean),
        sa.column("install_count", sa.Integer),
        sa.column("version", sa.String),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    op.bulk_insert(agent_table, [
        {
            "id": uuid.uuid4(), "name": "Customer Service Agent",
            "description": "A helpful customer service agent that can answer questions, handle complaints, and guide users.",
            "category": "customer-service",
            "tags": ["support", "customer-facing", "gpt-4o"],
            "system_prompt": "You are a helpful and empathetic customer service agent. Answer questions clearly, handle complaints professionally, and escalate when needed.",
            "config": {"temperature": 0.5, "max_tokens": 1024},
            "tools_config": None, "icon_name": "headset", "author_name": "AI Platform",
            "author_tenant_id": None, "is_public": True, "is_featured": True,
            "install_count": 0, "version": "1.0", "created_at": now, "updated_at": now,
        },
        {
            "id": uuid.uuid4(), "name": "Code Review Agent",
            "description": "An expert code reviewer that analyzes code for bugs, style issues, and security vulnerabilities.",
            "category": "coding",
            "tags": ["code-review", "security", "best-practices"],
            "system_prompt": "You are an expert code reviewer. Analyze code for bugs, security vulnerabilities, performance issues, and style violations. Provide constructive feedback.",
            "config": {"temperature": 0.3, "max_tokens": 2048},
            "tools_config": None, "icon_name": "code", "author_name": "AI Platform",
            "author_tenant_id": None, "is_public": True, "is_featured": True,
            "install_count": 0, "version": "1.0", "created_at": now, "updated_at": now,
        },
        {
            "id": uuid.uuid4(), "name": "Data Analyst Agent",
            "description": "Analyzes data, generates insights, and creates summaries from structured and unstructured data.",
            "category": "data-analysis",
            "tags": ["data", "analytics", "insights"],
            "system_prompt": "You are a data analysis expert. Help users understand their data, identify trends, generate insights, and create clear summaries.",
            "config": {"temperature": 0.4, "max_tokens": 2048},
            "tools_config": None, "icon_name": "chart-bar", "author_name": "AI Platform",
            "author_tenant_id": None, "is_public": True, "is_featured": False,
            "install_count": 0, "version": "1.0", "created_at": now, "updated_at": now,
        },
    ])

    op.bulk_insert(tool_table, [
        {
            "id": uuid.uuid4(), "name": "Web Search",
            "description": "Search the web for current information and return relevant results.",
            "category": "integration", "tags": ["search", "web", "bing"],
            "input_schema": {"type": "object", "properties": {"query": {"type": "string", "description": "Search query"}}, "required": ["query"]},
            "tool_type": "api", "config": None, "author_name": "AI Platform",
            "author_tenant_id": None, "is_public": True, "is_featured": True,
            "install_count": 0, "version": "1.0", "created_at": now, "updated_at": now,
        },
        {
            "id": uuid.uuid4(), "name": "Calculator",
            "description": "Perform mathematical calculations and return results.",
            "category": "utility", "tags": ["math", "calculator"],
            "input_schema": {"type": "object", "properties": {"expression": {"type": "string", "description": "Math expression to evaluate"}}, "required": ["expression"]},
            "tool_type": "function", "config": None, "author_name": "AI Platform",
            "author_tenant_id": None, "is_public": True, "is_featured": False,
            "install_count": 0, "version": "1.0", "created_at": now, "updated_at": now,
        },
        {
            "id": uuid.uuid4(), "name": "File Reader",
            "description": "Read and parse file contents from various formats (PDF, DOCX, TXT).",
            "category": "utility", "tags": ["file", "parser", "document"],
            "input_schema": {"type": "object", "properties": {"file_path": {"type": "string", "description": "Path to the file"}}, "required": ["file_path"]},
            "tool_type": "function", "config": None, "author_name": "AI Platform",
            "author_tenant_id": None, "is_public": True, "is_featured": False,
            "install_count": 0, "version": "1.0", "created_at": now, "updated_at": now,
        },
    ])


def downgrade() -> None:
    op.drop_table("tool_templates")
    op.drop_table("agent_templates")
