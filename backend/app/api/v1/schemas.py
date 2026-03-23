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


class AgentDataSourceResponse(BaseModel):
    id: UUID
    agent_id: UUID
    data_source_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}
