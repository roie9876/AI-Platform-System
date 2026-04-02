from typing import Optional, List, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator
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
    email: str = ""
    full_name: str = ""
    tenant_id: Optional[UUID] = None
    is_active: bool = True

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    detail: str
    code: str


# --- Agent Schemas ---

class TelegramGroupRule(BaseModel):
    """Per-group rule for Telegram."""
    group_name: str = ""  # Human-readable label (for UI only)
    group_id: str = ""  # Telegram group/supergroup ID
    policy: Literal["open", "allowlist", "blocked"] = "open"
    require_mention: bool = True
    allowed_users: List[str] = []
    instructions: str = ""  # Per-group agent instructions (appended to system prompt)


class OpenClawChannelConfig(BaseModel):
    """Channel configuration for OpenClaw agents."""
    telegram_enabled: bool = False
    telegram_bot_token: Optional[str] = None  # Raw token (stored in Key Vault, never persisted in DB)
    telegram_bot_token_secret: Optional[str] = None  # Key Vault secret name
    telegram_allowed_users: List[str] = []
    dm_policy: Literal["open", "allowlist", "pairing"] = "allowlist"
    telegram_group_rules: List[TelegramGroupRule] = []  # Per-group overrides


class OpenClawGmailConfig(BaseModel):
    """Gmail configuration for OpenClaw agents."""
    gmail_enabled: bool = False
    gmail_email: Optional[str] = None
    gmail_app_password: Optional[str] = None  # Raw app password (stored in Key Vault, never persisted in DB)
    gmail_app_password_secret: Optional[str] = None  # Key Vault secret name (for existing secrets)
    gmail_display_name: str = "OpenClaw Agent"


class WhatsAppGroupRule(BaseModel):
    """Per-group rule for WhatsApp."""
    group_name: str = ""  # Human-readable label (for UI only)
    group_jid: str = ""  # WhatsApp group JID (e.g. "120363012345678@g.us") or leave empty to add later
    policy: Literal["open", "allowlist", "blocked"] = "open"
    require_mention: bool = False
    allowed_phones: List[str] = []  # Only used when policy = "allowlist"
    instructions: str = ""  # Per-group agent instructions (appended to system prompt)


class OpenClawWhatsAppConfig(BaseModel):
    """WhatsApp configuration for OpenClaw agents."""
    whatsapp_enabled: bool = False
    whatsapp_dm_policy: Literal["open", "allowlist", "pairing"] = "open"
    whatsapp_group_policy: Literal["open", "allowlist"] = "open"
    whatsapp_allowed_phones: List[str] = []  # Phone numbers allowed to interact (DMs)
    whatsapp_group_rules: List[WhatsAppGroupRule] = []  # Per-group overrides


class OpenClawConfig(BaseModel):
    """OpenClaw-specific configuration embedded in agent."""
    channels: Optional[OpenClawChannelConfig] = None
    gmail: Optional[OpenClawGmailConfig] = None
    whatsapp: Optional[OpenClawWhatsAppConfig] = None
    enable_web_browsing: bool = True
    enable_shell: bool = False
    enable_deep_research: bool = False
    mcp_server_urls: List[str] = []  # MCP server URLs for tool access


class AgentCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    agent_type: Literal["standard", "openclaw"] = "standard"
    model_endpoint_id: Optional[UUID] = None
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=1024, ge=1, le=128000)
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    openclaw_config: Optional[OpenClawConfig] = None


class AgentUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    model_endpoint_id: Optional[UUID] = None
    temperature: Optional[float] = Field(default=None, ge=0, le=2)
    max_tokens: Optional[int] = Field(default=None, ge=1, le=128000)
    timeout_seconds: Optional[int] = Field(default=None, ge=1, le=300)
    openclaw_config: Optional[OpenClawConfig] = None


class AgentResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    agent_type: str = "standard"
    status: str = "active"
    status_message: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 1024
    timeout_seconds: int = 30
    model_endpoint_id: Optional[UUID] = None
    current_config_version: int = 1
    tenant_id: Optional[UUID] = None
    openclaw_config: Optional[OpenClawConfig] = None
    openclaw_instance_name: Optional[str] = None
    openclaw_gateway_url: Optional[str] = None
    whatsapp_status: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

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
    provider_type: str = ""
    endpoint_url: Optional[str] = None
    model_name: str = ""
    auth_type: str = "api_key"
    is_active: bool = True
    priority: int = 0
    tenant_id: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ModelEndpointListResponse(BaseModel):
    endpoints: List[ModelEndpointResponse]
    total: int


# --- AgentConfigVersion Schemas ---

class AgentConfigVersionResponse(BaseModel):
    id: UUID
    agent_id: UUID
    version_number: int = 1
    config_snapshot: dict = {}
    change_description: Optional[str] = None
    created_at: Optional[datetime] = None

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
    description: Optional[str] = None
    input_schema: dict = {}
    output_schema: Optional[dict] = None
    docker_image: Optional[str] = None
    execution_command: Optional[str] = None
    timeout_seconds: int = 30
    is_platform_tool: bool = False
    tenant_id: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ToolListResponse(BaseModel):
    tools: List[ToolResponse]
    total: int


class AgentToolAttachRequest(BaseModel):
    tool_id: UUID


class AgentToolResponse(BaseModel):
    id: UUID
    agent_id: Optional[UUID] = None
    tool_id: Optional[UUID] = None
    created_at: Optional[datetime] = None

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
    description: Optional[str] = None
    source_type: str = ""
    config: Optional[dict] = None
    status: str = "active"
    tenant_id: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DataSourceListResponse(BaseModel):
    data_sources: List[DataSourceResponse]
    total: int


class AgentDataSourceAttachRequest(BaseModel):
    data_source_id: UUID


# --- Document Schemas ---

class DocumentResponse(BaseModel):
    id: UUID
    data_source_id: Optional[UUID] = None
    filename: str = ""
    content_type: Optional[str] = None
    file_size: Optional[int] = None
    content_hash: Optional[str] = None
    status: str = "pending"
    chunk_count: int = 0
    tenant_id: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

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
    description: Optional[str] = None
    input_schema: dict = {}
    service_name: str = ""
    is_enabled: bool = True

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
    subscription_id: str = ""
    display_name: str = ""
    tenant_azure_id: Optional[str] = None
    state: str = "active"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


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
    agent_ids: Optional[List[str]] = None
    azure_subscription_id: Optional[UUID] = None
    resource_type: str = ""
    resource_name: str = ""
    resource_id: str = ""
    endpoint: Optional[str] = None
    region: Optional[str] = None
    auth_type: str = "api_key"
    health_status: str = "unknown"
    last_health_check: Optional[datetime] = None
    config: Optional[dict] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


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
    connector_type: str = ""
    category: str = ""
    provider: str = "Custom"
    icon_name: Optional[str] = None
    badges: Optional[List[str]] = None
    config_schema: Optional[dict] = None
    auth_types: Optional[List[str]] = None
    is_builtin: bool = False
    arm_resource_type: Optional[str] = None
    created_at: Optional[datetime] = None


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
    agent_id: Optional[UUID] = None
    data_source_id: Optional[UUID] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# --- Thread Schemas ---

class ThreadCreateRequest(BaseModel):
    agent_id: UUID
    title: Optional[str] = None


class ThreadUpdateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)


class ThreadResponse(BaseModel):
    id: UUID
    title: Optional[str] = None
    agent_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    tenant_id: Optional[UUID] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    message_count: int = 0
    last_message_preview: Optional[str] = None

    model_config = {"from_attributes": True}


class ThreadListResponse(BaseModel):
    threads: List[ThreadResponse]
    total: int


class ThreadMessageResponse(BaseModel):
    id: UUID
    thread_id: Optional[UUID] = None
    role: str = ""
    content: str = ""
    message_metadata: Optional[dict] = None
    sequence_number: int = 0
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ThreadMessagesResponse(BaseModel):
    messages: List[ThreadMessageResponse]
    total: int


# --- Memory Schemas ---

class AgentMemoryResponse(BaseModel):
    id: UUID
    agent_id: Optional[UUID] = None
    content: str = ""
    memory_type: str = "conversation"
    source_thread_id: Optional[UUID] = None
    created_at: Optional[datetime] = None

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
    workflow_id: Optional[UUID] = None
    agent_id: Optional[UUID] = None
    name: str = ""
    node_type: str = "agent"
    position_x: float = 0
    position_y: float = 0
    config: Optional[dict] = None
    execution_order: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class WorkflowEdgeCreateRequest(BaseModel):
    source_node_id: UUID
    target_node_id: UUID
    edge_type: str = Field(default="default", pattern=r"^(default|conditional|error)$")
    condition: Optional[dict] = None
    output_mapping: Optional[dict] = None


class WorkflowEdgeResponse(BaseModel):
    id: UUID
    workflow_id: Optional[UUID] = None
    source_node_id: Optional[UUID] = None
    target_node_id: Optional[UUID] = None
    edge_type: str = "default"
    condition: Optional[dict] = None
    output_mapping: Optional[dict] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

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
    workflow_type: str = "sequential"
    is_active: bool = True
    tenant_id: Optional[UUID] = None
    created_by: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

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
    workflow_id: Optional[UUID] = None
    status: str = "pending"
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    input_data: Optional[dict] = None
    output_data: Optional[dict] = None
    error: Optional[str] = None
    tenant_id: Optional[UUID] = None
    triggered_by: Optional[UUID] = None
    thread_id: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class WorkflowNodeExecutionResponse(BaseModel):
    id: UUID
    node_id: Optional[UUID] = None
    agent_id: Optional[UUID] = None
    status: str = "pending"
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    input_data: Optional[dict] = None
    output_data: Optional[dict] = None
    error: Optional[str] = None
    thread_id: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

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
    model_name: str = ""
    provider_type: str = ""
    input_price_per_1k: float = 0.0
    output_price_per_1k: float = 0.0
    currency: str = "USD"
    is_active: bool = True
    tenant_id: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

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
    name: str = ""
    alert_type: str = "budget_threshold"
    threshold_amount: float = 0.0
    period: str = "monthly"
    scope_type: str = "tenant"
    scope_id: Optional[UUID] = None
    is_active: bool = True
    last_triggered_at: Optional[datetime] = None
    tenant_id: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# --- Evaluation Schemas ---

class TestSuiteCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    agent_id: UUID


class TestSuiteResponse(BaseModel):
    id: UUID
    name: str = ""
    description: Optional[str] = None
    agent_id: Optional[UUID] = None
    tenant_id: Optional[UUID] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TestCaseCreate(BaseModel):
    input_message: str = Field(..., min_length=1)
    expected_output: Optional[str] = None
    expected_keywords: Optional[List[str]] = None
    metadata_: Optional[dict] = None
    order_index: int = 0


class TestCaseResponse(BaseModel):
    id: UUID
    test_suite_id: Optional[UUID] = None
    input_message: str = ""
    expected_output: Optional[str] = None
    expected_keywords: Optional[List[str]] = None
    order_index: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class EvaluationRunResponse(BaseModel):
    id: UUID
    test_suite_id: Optional[UUID] = None
    agent_id: Optional[UUID] = None
    config_version_id: Optional[UUID] = None
    status: str = "pending"
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    summary: Optional[dict] = None
    tenant_id: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class EvaluationResultResponse(BaseModel):
    id: UUID
    run_id: Optional[UUID] = None
    test_case_id: Optional[UUID] = None
    actual_output: Optional[str] = None
    score: Optional[float] = None
    metrics: Optional[dict] = None
    status: str = "pending"
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

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
    url: str = ""
    description: Optional[str] = None
    auth_type: str = "none"
    auth_header_name: Optional[str] = None
    is_active: bool = True
    status: str = "unknown"
    status_message: Optional[str] = None
    tenant_id: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class MCPServerListResponse(BaseModel):
    servers: List[MCPServerResponse]
    total: int


# --- MCP Discovered Tool Schemas ---

class MCPDiscoveredToolResponse(BaseModel):
    id: UUID
    server_id: Optional[UUID] = None
    tool_name: str = ""
    description: Optional[str] = None
    input_schema: Optional[dict] = None
    is_available: bool = True
    tenant_id: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

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
    agent_id: Optional[UUID] = None
    mcp_tool_id: Optional[UUID] = None
    tool_name: str = ""
    description: Optional[str] = None
    server_id: Optional[UUID] = None
    server_name: str = ""
    is_available: bool = True
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# --- Tenant Schemas ---

class TenantCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    admin_email: Optional[EmailStr] = None
    entra_group_id: Optional[str] = Field(default=None, description="Entra ID security group Object ID for this tenant")

    @field_validator("slug", mode="before")
    @classmethod
    def lowercase_slug(cls, v: str) -> str:
        if isinstance(v, str):
            return v.lower().strip()
        return v


class TenantUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    admin_email: Optional[EmailStr] = None
    entra_group_id: Optional[str] = None


class TenantSettingsUpdateRequest(BaseModel):
    display_name: Optional[str] = Field(default=None, max_length=255)
    allowed_providers: Optional[List[str]] = None
    token_quota: Optional[int] = Field(default=None, ge=0)
    feature_flags: Optional[dict] = None


class TenantStateTransitionRequest(BaseModel):
    state: str = Field(..., pattern=r"^(active|suspended|deactivated|deleted)$")


class TenantResponse(BaseModel):
    id: str
    name: str
    slug: str
    admin_email: str
    entra_group_id: Optional[str] = ""
    status: str
    settings: dict
    created_at: str
    updated_at: str


class TenantListResponse(BaseModel):
    tenants: List[TenantResponse]
