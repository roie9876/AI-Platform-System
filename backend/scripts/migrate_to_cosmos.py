"""
Data Migration: PostgreSQL → Cosmos DB

Reads all data from existing PostgreSQL database via SQLAlchemy
and writes to Cosmos DB containers via direct Cosmos SDK calls.

Usage:
    cd backend
    python -m scripts.migrate_to_cosmos --database-url postgresql+asyncpg://user:pass@host/db

Environment:
    COSMOS_ENDPOINT  — Cosmos DB account endpoint
    COSMOS_DATABASE  — Cosmos DB database name
"""
import asyncio
import argparse
import logging
import sys
from datetime import datetime, date
from typing import Any, Dict, List, Type
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.models import (
    Base,
    Tenant, User, RefreshToken, ModelEndpoint,
    Agent, AgentConfigVersion,
    Tool, AgentTool,
    DataSource, AgentDataSource,
    Document, DocumentChunk,
    AzureSubscription, AzureConnection, CatalogEntry,
    Thread, ThreadMessage, AgentMemory, ExecutionLog,
    Workflow, WorkflowNode, WorkflowEdge,
    WorkflowExecution, WorkflowNodeExecution,
    ModelPricing, CostAlert,
    TestSuite, TestCase, EvaluationRun, EvaluationResult,
    AgentTemplate, ToolTemplate,
    MCPServer, MCPDiscoveredTool, AgentMCPTool,
)
from app.repositories.cosmos_client import get_cosmos_container, close_cosmos_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Map SQLAlchemy model class → Cosmos DB container name
MODEL_CONTAINER_MAP: List[tuple[Type[Base], str]] = [
    (Tenant, "tenants"),
    (User, "users"),
    (RefreshToken, "refresh_tokens"),
    (ModelEndpoint, "model_endpoints"),
    (Agent, "agents"),
    (AgentConfigVersion, "agent_config_versions"),
    (Tool, "tools"),
    (AgentTool, "agent_tools"),
    (DataSource, "data_sources"),
    (AgentDataSource, "agent_data_sources"),
    (Document, "documents"),
    (DocumentChunk, "document_chunks"),
    (AzureSubscription, "azure_subscriptions"),
    (AzureConnection, "azure_connections"),
    (CatalogEntry, "catalog_entries"),
    (Thread, "threads"),
    (ThreadMessage, "thread_messages"),
    (AgentMemory, "agent_memories"),
    (ExecutionLog, "execution_logs"),
    (Workflow, "workflows"),
    (WorkflowNode, "workflow_nodes"),
    (WorkflowEdge, "workflow_edges"),
    (WorkflowExecution, "workflow_executions"),
    (WorkflowNodeExecution, "workflow_node_executions"),
    (ModelPricing, "model_pricing"),
    (CostAlert, "cost_alerts"),
    (TestSuite, "test_suites"),
    (TestCase, "test_cases"),
    (EvaluationRun, "evaluation_runs"),
    (EvaluationResult, "evaluation_results"),
    (AgentTemplate, "agent_templates"),
    (ToolTemplate, "tool_templates"),
    (MCPServer, "mcp_servers"),
    (MCPDiscoveredTool, "mcp_discovered_tools"),
    (AgentMCPTool, "agent_mcp_tools"),
]


def serialize_value(value: Any) -> Any:
    """Convert a Python value to a Cosmos DB-compatible JSON value."""
    if value is None:
        return None
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, (int, float, bool, str)):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def serialize_row(row: Base) -> Dict[str, Any]:
    """Convert a SQLAlchemy model instance to a Cosmos DB document dict.

    - UUID fields → str
    - datetime fields → ISO 8601 string
    - JSONB fields → dict/list (already native)
    - id field → str (Cosmos requires string id)
    - tenant_id preserved as partition key
    """
    doc: Dict[str, Any] = {}
    mapper = row.__class__.__mapper__  # type: ignore[attr-defined]

    for column in mapper.columns:
        key = column.key
        value = getattr(row, key, None)
        doc[key] = serialize_value(value)

    # Cosmos DB requires 'id' as string
    if "id" in doc and doc["id"] is not None:
        doc["id"] = str(doc["id"])

    return doc


async def migrate_table(
    session_maker: async_sessionmaker,
    model_class: Type[Base],
    container_name: str,
    batch_size: int = 100,
) -> tuple[int, int]:
    """Read all rows from PostgreSQL table and upsert into Cosmos container.

    Returns (success_count, failure_count).
    """
    container = await get_cosmos_container(container_name)
    success = 0
    failure = 0

    async with session_maker() as session:
        result = await session.execute(select(model_class))
        rows = list(result.scalars().all())

    logger.info("  Found %d rows in %s", len(rows), model_class.__tablename__)

    for row in rows:
        doc = serialize_row(row)
        try:
            await container.upsert_item(doc)
            success += 1
        except Exception as e:
            failure += 1
            logger.error(
                "  Failed to upsert %s id=%s: %s",
                container_name, doc.get("id", "?"), str(e)[:200],
            )

    return success, failure


async def main(database_url: str, dry_run: bool = False) -> None:
    """Run the full migration from PostgreSQL to Cosmos DB."""
    logger.info("=" * 60)
    logger.info("PostgreSQL → Cosmos DB Migration")
    logger.info("=" * 60)
    logger.info("Source: %s", database_url.split("@")[-1] if "@" in database_url else "(hidden)")
    logger.info("Dry run: %s", dry_run)
    logger.info("")

    engine = create_async_engine(database_url, echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    total_success = 0
    total_failure = 0
    table_results: List[Dict[str, Any]] = []

    try:
        for model_class, container_name in MODEL_CONTAINER_MAP:
            table_name = getattr(model_class, "__tablename__", container_name)
            logger.info("Migrating %s → %s ...", table_name, container_name)

            if dry_run:
                async with session_maker() as session:
                    result = await session.execute(select(model_class))
                    count = len(list(result.scalars().all()))
                logger.info("  [DRY RUN] Would migrate %d rows", count)
                table_results.append({"table": table_name, "container": container_name, "count": count})
                continue

            success, failure = await migrate_table(
                session_maker, model_class, container_name,
            )
            total_success += success
            total_failure += failure
            table_results.append({
                "table": table_name,
                "container": container_name,
                "success": success,
                "failure": failure,
            })
            logger.info("  ✓ %d succeeded, %d failed", success, failure)

    finally:
        await engine.dispose()
        await close_cosmos_client()

    # Summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("Migration Summary")
    logger.info("=" * 60)
    for tr in table_results:
        if dry_run:
            logger.info("  %s → %s: %d rows", tr["table"], tr["container"], tr["count"])
        else:
            status = "✓" if tr["failure"] == 0 else "✗"
            logger.info(
                "  %s %s → %s: %d ok, %d failed",
                status, tr["table"], tr["container"], tr["success"], tr["failure"],
            )

    if not dry_run:
        logger.info("")
        logger.info("Total: %d migrated, %d failed", total_success, total_failure)
        if total_failure > 0:
            logger.warning("Some items failed to migrate. Review logs above.")
            sys.exit(1)
        else:
            logger.info("Migration completed successfully!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Migrate data from PostgreSQL to Cosmos DB",
    )
    parser.add_argument(
        "--database-url",
        required=True,
        help="PostgreSQL connection string (postgresql+asyncpg://user:pass@host/db)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count rows without actually migrating",
    )
    args = parser.parse_args()
    asyncio.run(main(args.database_url, dry_run=args.dry_run))
