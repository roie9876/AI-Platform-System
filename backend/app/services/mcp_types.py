"""
MCP (Model Context Protocol) type definitions.

Pydantic v2 models for JSON-RPC 2.0 messaging and MCP protocol operations
(initialize, tools/list, tools/call) over Streamable HTTP transport.
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# JSON-RPC 2.0 base types
# ---------------------------------------------------------------------------

class JsonRpcRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    jsonrpc: Literal["2.0"] = "2.0"
    id: int
    method: str
    params: Optional[Dict[str, Any]] = None


class JsonRpcNotification(BaseModel):
    model_config = ConfigDict(extra="allow")

    jsonrpc: Literal["2.0"] = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = None


class JsonRpcErrorDetail(BaseModel):
    model_config = ConfigDict(extra="allow")

    code: int
    message: str
    data: Optional[Any] = None


class JsonRpcResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    jsonrpc: Literal["2.0"] = "2.0"
    id: int
    result: Optional[Any] = None


class JsonRpcErrorResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    jsonrpc: Literal["2.0"] = "2.0"
    id: Optional[int] = None
    error: JsonRpcErrorDetail


# ---------------------------------------------------------------------------
# MCP Initialize
# ---------------------------------------------------------------------------

class ClientCapabilities(BaseModel):
    model_config = ConfigDict(extra="allow")

    roots: Optional[Dict[str, Any]] = None
    sampling: Optional[Dict[str, Any]] = None


class ClientInfo(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    version: str


class InitializeParams(BaseModel):
    model_config = ConfigDict(extra="allow")

    protocolVersion: str = "2025-03-26"
    capabilities: ClientCapabilities = ClientCapabilities()
    clientInfo: ClientInfo = ClientInfo(name="ai-platform", version="1.0.0")


class ServerCapabilities(BaseModel):
    model_config = ConfigDict(extra="allow")

    tools: Optional[Dict[str, Any]] = None


class ServerInfo(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    version: str


class InitializeResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    protocolVersion: str
    capabilities: ServerCapabilities
    serverInfo: ServerInfo


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------

class MCPToolInputSchema(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: Literal["object"] = "object"
    properties: Optional[Dict[str, Any]] = None
    required: Optional[List[str]] = None


class MCPToolInfo(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    description: Optional[str] = None
    inputSchema: MCPToolInputSchema = MCPToolInputSchema()


class ListToolsResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    tools: List[MCPToolInfo]
    nextCursor: Optional[str] = None


class ToolCallParams(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    arguments: Optional[Dict[str, Any]] = None


class ContentBlock(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str
    text: Optional[str] = None
    data: Optional[str] = None
    mimeType: Optional[str] = None


class ToolCallResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    content: List[ContentBlock]
    isError: Optional[bool] = None
