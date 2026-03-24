from typing import Optional, List

from pydantic import BaseModel, EmailStr, Field
from uuid import UUID
from datetime import datetime


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    tenant_slug: str


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    tenant_id: UUID
    is_active: bool

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    detail: str
    code: str


# --- Agent Schemas ---

class AgentCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    model_endpoint_id: Optional[UUID] = None
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=1024, ge=1, le=128000)
    timeout_seconds: int = Field(default=30, ge=1, le=300)


class AgentUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    model_endpoint_id: Optional[UUID] = None
    temperature: Optional[float] = Field(default=None, ge=0, le=2)
    max_tokens: Optional[int] = Field(default=None, ge=1, le=128000)
    timeout_seconds: Optional[int] = Field(default=None, ge=1, le=300)


class AgentResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    system_prompt: Optional[str]
    status: str
    temperature: float
    max_tokens: int
    timeout_seconds: int
    model_endpoint_id: Optional[UUID]
    current_config_version: int
    tenant_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentListResponse(BaseModel):
    agents: List[AgentResponse]
    total: int


# --- ModelEndpoint Schemas ---

VALID_PROVIDER_TYPES = {"azure_openai", "openai", "anthropic", "custom"}
VALID_AUTH_TYPES = {"entra_id", "api_key"}


class ModelEndpointCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    provider_type: str = Field(..., min_length=1)
    endpoint_url: Optional[str] = None
    model_name: str = Field(..., min_length=1, max_length=255)
    api_key: Optional[str] = None
    auth_type: str = Field(..., min_length=1)
    priority: int = Field(default=0, ge=0)


class ModelEndpointUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    provider_type: Optional[str] = None
    endpoint_url: Optional[str] = None
    model_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    api_key: Optional[str] = None
    auth_type: Optional[str] = None
    priority: Optional[int] = Field(default=None, ge=0)


class ModelEndpointResponse(BaseModel):
    id: UUID
    name: str
    provider_type: str
    endpoint_url: Optional[str]
    model_name: str
    auth_type: str
    is_active: bool
    priority: int
    tenant_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ModelEndpointListResponse(BaseModel):
    endpoints: List[ModelEndpointResponse]
    total: int


# --- AgentConfigVersion Schemas ---

class AgentConfigVersionResponse(BaseModel):
    id: UUID
    agent_id: UUID
    version_number: int
    config_snapshot: dict
    change_description: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Chat Schemas ---

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    conversation_history: Optional[List[ChatMessage]] = None
    thread_id: Optional[UUID] = None


# --- Tool Schemas ---

class ToolCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    input_schema: dict
    output_schema: Optional[dict] = None
    docker_image: Optional[str] = Field(default=None, max_length=512)
    execution_command: Optional[str] = Field(default=None, max_length=1024)
    timeout_seconds: int = Field(default=30, ge=1, le=300)


class ToolUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    input_schema: Optional[dict] = None
    output_schema: Optional[dict] = None
    docker_image: Optional[str] = Field(default=None, max_length=512)
    execution_command: Optional[str] = Field(default=None, max_length=1024)
    timeout_seconds: Optional[int] = Field(default=None, ge=1, le=300)


class ToolResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    input_schema: dict
    output_schema: Optional[dict]
    docker_image: Optional[str]
    execution_command: Optional[str]
    timeout_seconds: int
    is_platform_tool: bool
    tenant_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ToolListResponse(BaseModel):
    tools: List[ToolResponse]
    total: int


class AgentToolAttachRequest(BaseModel):
    tool_id: UUID


class AgentToolResponse(BaseModel):
    id: UUID
    agent_id: UUID
    tool_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


# --- DataSource Schemas ---

class DataSourceCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    source_type: str = Field(..., min_length=1)
    config: Optional[dict] = None
    credentials: Optional[str] = None


class DataSourceUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    config: Optional[dict] = None


class DataSourceResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    source_type: str
    config: Optional[dict]
    status: str
    tenant_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DataSourceListResponse(BaseModel):
    data_sources: List[DataSourceResponse]
    total: int


class AgentDataSourceAttachRequest(BaseModel):
    data_source_id: UUID


# --- Document Schemas ---

class DocumentResponse(BaseModel):
    id: UUID
    data_source_id: UUID
    filename: str
    content_type: Optional[str]
    file_size: Optional[int]
    content_hash: Optional[str]
    status: str
    chunk_count: int
    tenant_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]
    total: int


class IngestURLRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=2048)


# --- AI Services Schemas ---

class PlatformToolResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    input_schema: dict
    service_name: str
    is_enabled: bool

    model_config = {"from_attributes": True}


class PlatformToolListResponse(BaseModel):
    tools: List[PlatformToolResponse]
    total: int


class PlatformToolToggleRequest(BaseModel):
    tool_id: UUID
    enabled: bool


# --- Azure Subscription Schemas ---

class AzureSubscriptionCreate(BaseModel):
    subscription_id: str
    display_name: str
    tenant_azure_id: str
    access_token: str
    refresh_token: Optional[str] = None


class AzureSubscriptionResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    subscription_id: str
    display_name: str
    tenant_azure_id: str
    state: str
    created_at: datetime
    updated_at: datetime


class DiscoveredResource(BaseModel):
    resource_id: str
    name: str
    resource_type: str
    region: str
    resource_group: Optional[str] = None


class ResourceDiscoveryResponse(BaseModel):
    subscription_id: str
    resource_type: str
    resources: List[DiscoveredResource]
    count: int


# --- Azure Connection Schemas ---

class AzureConnectionCreate(BaseModel):
    agent_id: Optional[UUID] = None
    azure_subscription_id: UUID
    resource_type: str
    resource_name: str
    resource_id: str
    endpoint: Optional[str] = None
    region: Optional[str] = None
    auth_type: str = "api_key"
    credentials: Optional[str] = None


class AzureConnectionUpdate(BaseModel):
    auth_type: Optional[str] = None
    credentials: Optional[str] = None
    config: Optional[dict] = None


class AzureConnectionResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    agent_id: Optional[UUID] = None
    azure_subscription_id: UUID
    resource_type: str
    resource_name: str
    resource_id: str
    endpoint: Optional[str] = None
    region: Optional[str] = None
    auth_type: str
    health_status: str
    last_health_check: Optional[datetime] = None
    config: Optional[dict] = None
    created_at: datetime
    updated_at: datetime


# --- Catalog Schemas ---

class CatalogEntryCreate(BaseModel):
    name: str
    description: Optional[str] = None
    connector_type: str
    category: str
    provider: str = "Custom"
    icon_name: Optional[str] = None
    badges: Optional[List[str]] = None
    config_schema: Optional[dict] = None
    auth_types: Optional[List[str]] = None


class CatalogEntryResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    name: str
    description: Optional[str] = None
    connector_type: str
    category: str
    provider: str
    icon_name: Optional[str] = None
    badges: Optional[List[str]] = None
    config_schema: Optional[dict] = None
    auth_types: Optional[List[str]] = None
    is_builtin: bool
    arm_resource_type: Optional[str] = None
    created_at: datetime


# --- Knowledge / AI Search Schemas ---

class SearchIndex(BaseModel):
    name: str
    document_count: Optional[int] = None


class SearchIndexListResponse(BaseModel):
    connection_id: UUID
    resource_name: str
    indexes: List[SearchIndex]
    count: int


class SelectIndexesRequest(BaseModel):
    index_names: List[str]
    knowledge_name: Optional[str] = None


class AgentKnowledgeIndexInfo(BaseModel):
    connection_id: UUID
    resource_name: str
    knowledge_name: Optional[str] = None
    index_names: List[str]


class AgentKnowledgeResponse(BaseModel):
    agent_id: UUID
    connections: List[AgentKnowledgeIndexInfo]
    total_indexes: int


class AgentDataSourceResponse(BaseModel):
    id: UUID
    agent_id: UUID
    data_source_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Thread Schemas ---

class ThreadCreateRequest(BaseModel):
    agent_id: UUID
    title: Optional[str] = None


class ThreadUpdateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)


class ThreadResponse(BaseModel):
    id: UUID
    title: Optional[str]
    agent_id: UUID
    user_id: UUID
    tenant_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    last_message_preview: Optional[str] = None

    model_config = {"from_attributes": True}


class ThreadListResponse(BaseModel):
    threads: List[ThreadResponse]
    total: int


class ThreadMessageResponse(BaseModel):
    id: UUID
    thread_id: UUID
    role: str
    content: str
    message_metadata: Optional[dict] = None
    sequence_number: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ThreadMessagesResponse(BaseModel):
    messages: List[ThreadMessageResponse]
    total: int


# --- Memory Schemas ---

class AgentMemoryResponse(BaseModel):
    id: UUID
    agent_id: UUID
    content: str
    memory_type: str
    source_thread_id: Optional[UUID] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentMemoryListResponse(BaseModel):
    memories: List[AgentMemoryResponse]
    total: int


# --- Workflow Schemas ---

class WorkflowNodeConfig(BaseModel):
    input_mapping: Optional[dict] = None
    system_prompt_override: Optional[str] = None
    timeout_override: Optional[int] = None


class WorkflowNodeCreateRequest(BaseModel):
    agent_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    node_type: str = Field(default="agent", pattern=r"^(agent|sub_agent|aggregator|router)$")
    position_x: float = 0
    position_y: float = 0
    config: Optional[WorkflowNodeConfig] = None
    execution_order: int = 0


class WorkflowNodeResponse(BaseModel):
    id: UUID
    workflow_id: UUID
    agent_id: UUID
    name: str
    node_type: str
    position_x: float
    position_y: float
    config: Optional[dict] = None
    execution_order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkflowEdgeCreateRequest(BaseModel):
    source_node_id: UUID
    target_node_id: UUID
    edge_type: str = Field(default="default", pattern=r"^(default|conditional|error)$")
    condition: Optional[dict] = None
    output_mapping: Optional[dict] = None


class WorkflowEdgeResponse(BaseModel):
    id: UUID
    workflow_id: UUID
    source_node_id: UUID
    target_node_id: UUID
    edge_type: str
    condition: Optional[dict] = None
    output_mapping: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkflowCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    workflow_type: str = Field(default="sequential", pattern=r"^(sequential|parallel|autonomous|custom)$")
    nodes: Optional[List[WorkflowNodeCreateRequest]] = None
    edges: Optional[List[WorkflowEdgeCreateRequest]] = None


class WorkflowUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    workflow_type: Optional[str] = Field(default=None, pattern=r"^(sequential|parallel|autonomous|custom)$")


class WorkflowResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    workflow_type: str
    is_active: bool
    tenant_id: UUID
    created_by: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkflowDetailResponse(WorkflowResponse):
    nodes: List[WorkflowNodeResponse] = []
    edges: List[WorkflowEdgeResponse] = []


class WorkflowListResponse(BaseModel):
    workflows: List[WorkflowResponse]
    total: int


class WorkflowExecuteRequest(BaseModel):
    message: str = Field(..., min_length=1)
    input_data: Optional[dict] = None


class WorkflowExecutionResponse(BaseModel):
    id: UUID
    workflow_id: UUID
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    input_data: Optional[dict] = None
    output_data: Optional[dict] = None
    error: Optional[str] = None
    tenant_id: UUID
    triggered_by: UUID
    thread_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkflowNodeExecutionResponse(BaseModel):
    id: UUID
    node_id: UUID
    agent_id: UUID
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    input_data: Optional[dict] = None
    output_data: Optional[dict] = None
    error: Optional[str] = None
    thread_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkflowExecutionDetailResponse(WorkflowExecutionResponse):
    node_executions: List[WorkflowNodeExecutionResponse] = []


class WorkflowExecutionListResponse(BaseModel):
    executions: List[WorkflowExecutionResponse]
    total: int


# --- Observability Schemas ---

class DashboardSummaryResponse(BaseModel):
    total_requests: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    avg_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    success_count: int = 0
    error_count: int = 0
    requests_per_minute: float = 0.0


class TokenTimeSeriesItem(BaseModel):
    time: datetime
    input_tokens: int
    output_tokens: int
    total_tokens: int


class TokenTimeSeriesResponse(BaseModel):
    data: List[TokenTimeSeriesItem]


class CostBreakdownItem(BaseModel):
    name: str
    total_tokens: int
    total_cost: float
    request_count: int


class CostBreakdownResponse(BaseModel):
    data: List[CostBreakdownItem]


class ExecutionLogItem(BaseModel):
    id: UUID
    event_type: str
    duration_ms: Optional[int] = None
    token_count: Optional[dict] = None
    model_name: Optional[str] = None
    agent_name: Optional[str] = None
    created_at: Optional[datetime] = None


class ExecutionLogListResponse(BaseModel):
    logs: List[ExecutionLogItem]
    total: int


class ModelPricingCreate(BaseModel):
    model_name: str = Field(..., min_length=1, max_length=255)
    provider_type: str = Field(..., min_length=1, max_length=50)
    input_price_per_1k: float = Field(..., ge=0)
    output_price_per_1k: float = Field(..., ge=0)
    currency: str = Field(default="USD", max_length=10)


class ModelPricingResponse(BaseModel):
    id: UUID
    model_name: str
    provider_type: str
    input_price_per_1k: float
    output_price_per_1k: float
    currency: str
    is_active: bool
    tenant_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CostAlertCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    alert_type: str = Field(..., pattern=r"^(budget_threshold|spike_detection)$")
    threshold_amount: float = Field(..., gt=0)
    period: str = Field(..., pattern=r"^(daily|weekly|monthly)$")
    scope_type: str = Field(..., pattern=r"^(agent|tenant|model)$")
    scope_id: Optional[UUID] = None


class CostAlertResponse(BaseModel):
    id: UUID
    name: str
    alert_type: str
    threshold_amount: float
    period: str
    scope_type: str
    scope_id: Optional[UUID] = None
    is_active: bool
    last_triggered_at: Optional[datetime] = None
    tenant_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Evaluation Schemas ---

class TestSuiteCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    agent_id: UUID


class TestSuiteResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    agent_id: UUID
    tenant_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TestCaseCreate(BaseModel):
    input_message: str = Field(..., min_length=1)
    expected_output: Optional[str] = None
    expected_keywords: Optional[List[str]] = None
    metadata_: Optional[dict] = None
    order_index: int = 0


class TestCaseResponse(BaseModel):
    id: UUID
    test_suite_id: UUID
    input_message: str
    expected_output: Optional[str] = None
    expected_keywords: Optional[List[str]] = None
    order_index: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EvaluationRunResponse(BaseModel):
    id: UUID
    test_suite_id: UUID
    agent_id: UUID
    config_version_id: Optional[UUID] = None
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    summary: Optional[dict] = None
    tenant_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EvaluationResultResponse(BaseModel):
    id: UUID
    run_id: UUID
    test_case_id: UUID
    actual_output: Optional[str] = None
    score: Optional[float] = None
    metrics: Optional[dict] = None
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Marketplace Schemas ──


class AgentTemplateResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    icon_name: Optional[str] = None
    author_name: Optional[str] = None
    install_count: int = 0
    version: str = "1.0"
    is_featured: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentTemplateDetailResponse(AgentTemplateResponse):
    system_prompt: Optional[str] = None
    config: Optional[dict] = None
    tools_config: Optional[dict] = None
    updated_at: datetime


class PublishAgentTemplateRequest(BaseModel):
    agent_id: UUID
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None


class ToolTemplateResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    tool_type: str
    install_count: int = 0
    version: str = "1.0"
    is_featured: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class PublishToolTemplateRequest(BaseModel):
    tool_id: UUID
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None


# --- MCP Server Schemas ---

class MCPServerCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    url: str = Field(..., min_length=1)
    description: Optional[str] = None
    auth_type: str = Field(default="none", pattern="^(none|bearer|api_key|custom_header)$")
    auth_header_name: Optional[str] = None
    auth_credential_ref: Optional[str] = None


class MCPServerUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    url: Optional[str] = Field(default=None, min_length=1)
    description: Optional[str] = None
    auth_type: Optional[str] = Field(default=None, pattern="^(none|bearer|api_key|custom_header)$")
    auth_header_name: Optional[str] = None
    auth_credential_ref: Optional[str] = None
    is_active: Optional[bool] = None


class MCPServerResponse(BaseModel):
    id: UUID
    name: str
    url: str
    description: Optional[str] = None
    auth_type: str
    auth_header_name: Optional[str] = None
    is_active: bool
    status: str
    status_message: Optional[str] = None
    tenant_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MCPServerListResponse(BaseModel):
    servers: List[MCPServerResponse]
    total: int


# --- MCP Discovered Tool Schemas ---

class MCPDiscoveredToolResponse(BaseModel):
    id: UUID
    server_id: UUID
    tool_name: str
    description: Optional[str] = None
    input_schema: Optional[dict] = None
    is_available: bool
    tenant_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MCPDiscoveredToolListResponse(BaseModel):
    tools: List[MCPDiscoveredToolResponse]
    total: int


class MCPDiscoverySummaryResponse(BaseModel):
    servers_scanned: int
    tools_discovered: dict


# --- Agent MCP Tool Schemas ---

class AgentMCPToolAttachRequest(BaseModel):
    mcp_tool_id: UUID


class AgentMCPToolResponse(BaseModel):
    id: UUID
    agent_id: UUID
    mcp_tool_id: UUID
    tool_name: str
    description: Optional[str] = None
    server_id: UUID
    server_name: str
    is_available: bool
    created_at: datetime

    model_config = {"from_attributes": True}
