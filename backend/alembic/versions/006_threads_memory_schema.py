"""Add threads, thread_messages, agent_memories, execution_logs tables with pgvector

Revision ID: 006
Revises: 005
Create Date: 2025-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Threads table
    op.create_table(
        "threads",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_threads_agent_id", "threads", ["agent_id"])
    op.create_index("ix_threads_user_id", "threads", ["user_id"])
    op.create_index("ix_threads_tenant_id", "threads", ["tenant_id"])

    # Thread messages table
    op.create_table(
        "thread_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("thread_id", UUID(as_uuid=True), sa.ForeignKey("threads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("message_metadata", JSONB, nullable=True),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("thread_id", "sequence_number", name="uq_thread_sequence"),
    )
    op.create_index("ix_thread_messages_thread_id", "thread_messages", ["thread_id"])

    # Agent memories table
    op.create_table(
        "agent_memories",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("memory_type", sa.String(50), default="knowledge", nullable=False),
        sa.Column("source_thread_id", UUID(as_uuid=True), sa.ForeignKey("threads.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    # Add vector column via raw SQL (pgvector type not supported by alembic create_table)
    op.execute("ALTER TABLE agent_memories ADD COLUMN embedding vector(1536)")
    op.create_index("ix_agent_memories_agent_id", "agent_memories", ["agent_id"])
    op.create_index("ix_agent_memories_user_id", "agent_memories", ["user_id"])
    op.create_index("ix_agent_memories_tenant_id", "agent_memories", ["tenant_id"])
    # HNSW index for cosine similarity search
    op.execute(
        "CREATE INDEX ix_agent_memories_embedding ON agent_memories "
        "USING hnsw (embedding vector_cosine_ops)"
    )

    # Execution logs table
    op.create_table(
        "execution_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("thread_id", UUID(as_uuid=True), sa.ForeignKey("threads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message_id", UUID(as_uuid=True), sa.ForeignKey("thread_messages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("state_snapshot", JSONB, nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("token_count", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_execution_logs_thread_id", "execution_logs", ["thread_id"])


def downgrade() -> None:
    op.drop_table("execution_logs")
    op.drop_table("agent_memories")
    op.drop_table("thread_messages")
    op.drop_table("threads")
    op.execute("DROP EXTENSION IF EXISTS vector")
