# DEPRECATED: SQLAlchemy models — data access now uses Cosmos DB repositories (app.repositories).
# These models are retained for the PostgreSQL → Cosmos DB migration script (scripts/migrate_to_cosmos.py)
# and as schema documentation. They will be removed once migration is verified.

from app.models.base import Base
from app.models.tenant import Tenant
from app.models.user import User
from app.models.refresh_token import RefreshToken
from app.models.model_endpoint import ModelEndpoint
from app.models.agent import Agent
from app.models.agent_config_version import AgentConfigVersion
from app.models.tool import Tool, AgentTool
from app.models.data_source import DataSource, AgentDataSource
from app.models.document import Document, DocumentChunk
from app.models.azure_subscription import AzureSubscription
from app.models.azure_connection import AzureConnection
from app.models.catalog_entry import CatalogEntry
from app.models.thread import Thread
from app.models.thread_message import ThreadMessage
from app.models.agent_memory import AgentMemory
from app.models.execution_log import ExecutionLog
from app.models.workflow import Workflow, WorkflowNode, WorkflowEdge
from app.models.workflow_execution import WorkflowExecution, WorkflowNodeExecution
from app.models.cost_config import ModelPricing, CostAlert
from app.models.evaluation import TestSuite, TestCase, EvaluationRun, EvaluationResult
from app.models.marketplace import AgentTemplate, ToolTemplate
from app.models.mcp_server import MCPServer
from app.models.mcp_discovered_tool import MCPDiscoveredTool
from app.models.agent_mcp_tool import AgentMCPTool

__all__ = [
    "Base", "Tenant", "User", "RefreshToken", "ModelEndpoint",
    "Agent", "AgentConfigVersion",
    "Tool", "AgentTool",
    "DataSource", "AgentDataSource",
    "Document", "DocumentChunk",
    "AzureSubscription", "AzureConnection", "CatalogEntry",
    "Thread", "ThreadMessage", "AgentMemory", "ExecutionLog",
    "Workflow", "WorkflowNode", "WorkflowEdge",
    "WorkflowExecution", "WorkflowNodeExecution",
    "ModelPricing", "CostAlert",
    "TestSuite", "TestCase", "EvaluationRun", "EvaluationResult",
    "AgentTemplate", "ToolTemplate",
    "MCPServer", "MCPDiscoveredTool", "AgentMCPTool",
]
