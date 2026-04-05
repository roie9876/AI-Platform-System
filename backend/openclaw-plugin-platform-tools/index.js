/**
 * AI Platform Tools — OpenClaw plugin that bridges to the platform's
 * MCP HTTP server. Registers memory and config tools as native
 * OpenClaw tools so Azure OpenAI agents can use them.
 *
 * Environment: MCP_PLATFORM_TOOLS_URL (default: in-cluster service URL)
 */

import { Type } from "@sinclair/typebox";

const MCP_URL =
  process.env.MCP_PLATFORM_TOOLS_URL ||
  "http://mcp-platform-tools.aiplatform.svc.cluster.local:8085/mcp";

// ---------------------------------------------------------------------------
//  MCP JSON-RPC client helpers
// ---------------------------------------------------------------------------

let sessionId;

async function mcpCall(method, params) {
  const id = Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
  const body = JSON.stringify({ jsonrpc: "2.0", id, method, params });
  const headers = {
    "Content-Type": "application/json",
    Accept: "application/json, text/event-stream",
  };
  if (sessionId) headers["Mcp-Session-Id"] = sessionId;

  const res = await fetch(MCP_URL, { method: "POST", headers, body });
  const sid = res.headers.get("mcp-session-id");
  if (sid) sessionId = sid;

  const ct = res.headers.get("content-type") || "";
  if (ct.includes("text/event-stream")) {
    const text = await res.text();
    for (const line of text.split("\n")) {
      if (line.startsWith("data: ")) {
        const data = JSON.parse(line.slice(6));
        if (data.id === id) return data;
      }
    }
  }
  return await res.json();
}

async function callTool(name, args) {
  // Initialize session if needed
  if (!sessionId) {
    await mcpCall("initialize", {
      protocolVersion: "2025-03-26",
      capabilities: {},
      clientInfo: { name: "openclaw-platform-tools", version: "1.0.0" },
    });
  }
  const result = await mcpCall("tools/call", { name, arguments: args });
  if (result.error) throw new Error(result.error.message || "MCP tool error");
  return result.result;
}

// ---------------------------------------------------------------------------
//  JSON result helper (matches OpenClaw tool result format)
// ---------------------------------------------------------------------------

function jsonResult(payload) {
  return {
    content: [{ type: "text", text: JSON.stringify(payload, null, 2) }],
    details: payload,
  };
}

// ---------------------------------------------------------------------------
//  Tool definitions
// ---------------------------------------------------------------------------

function createMemoryStoreSchema() {
  return Type.Object(
    {
      tenant_id: Type.String({ description: "Tenant identifier" }),
      agent_id: Type.String({ description: "Agent identifier" }),
      content: Type.String({ description: "Memory content to store" }),
      memory_type: Type.Optional(
        Type.String({
          description: 'Type of memory: "knowledge", "preference", "fact"',
        })
      ),
      user_id: Type.Optional(Type.String({ description: "Associated user" })),
      source: Type.Optional(
        Type.String({ description: "Source of the memory" })
      ),
    },
    { additionalProperties: false }
  );
}

function createMemorySearchSchema() {
  return Type.Object(
    {
      tenant_id: Type.String({ description: "Tenant identifier" }),
      agent_id: Type.String({ description: "Agent identifier" }),
      query: Type.String({ description: "Semantic search query" }),
      top_k: Type.Optional(
        Type.Number({ description: "Number of results (default: 5)" })
      ),
      memory_type: Type.Optional(
        Type.String({ description: "Filter by memory type" })
      ),
    },
    { additionalProperties: false }
  );
}

function createStructuredStoreSchema() {
  return Type.Object(
    {
      tenant_id: Type.String({ description: "Tenant identifier" }),
      agent_id: Type.String({ description: "Agent identifier" }),
      key: Type.String({ description: "Key for the structured memory" }),
      value: Type.String({ description: "Value to store" }),
      category: Type.Optional(
        Type.String({ description: 'Category (default: "preference")' })
      ),
    },
    { additionalProperties: false }
  );
}

function createStructuredGetSchema() {
  return Type.Object(
    {
      tenant_id: Type.String({ description: "Tenant identifier" }),
      agent_id: Type.String({ description: "Agent identifier" }),
      key: Type.Optional(Type.String({ description: "Key to retrieve" })),
      category: Type.Optional(
        Type.String({ description: "Filter by category" })
      ),
    },
    { additionalProperties: false }
  );
}

function createGroupInstructionsSchema() {
  return Type.Object(
    {
      tenant_id: Type.String({ description: "Tenant identifier" }),
      agent_id: Type.String({ description: "Agent identifier" }),
      group_jid: Type.String({ description: "WhatsApp group JID" }),
    },
    { additionalProperties: false }
  );
}

function createAgentConfigSchema() {
  return Type.Object(
    {
      tenant_id: Type.String({ description: "Tenant identifier" }),
      agent_id: Type.String({ description: "Agent identifier" }),
    },
    { additionalProperties: false }
  );
}

function createListGroupsSchema() {
  return Type.Object(
    {
      tenant_id: Type.String({ description: "Tenant identifier" }),
      agent_id: Type.String({ description: "Agent identifier" }),
    },
    { additionalProperties: false }
  );
}

// ---------------------------------------------------------------------------
//  Plugin entry (definePluginEntry inline — avoids hash-dependent imports)
// ---------------------------------------------------------------------------

export default {
  id: "platform-tools",
  name: "AI Platform Tools",
  description:
    "Bridges AI Platform MCP tools (memory, config) into the OpenClaw agent",
  configSchema: {
    type: "object",
    additionalProperties: false,
    properties: {},
  },
  register(api) {
    api.registerTool({
      name: "platform_memory_store",
      label: "Store Memory",
      description:
        "Store a memory with semantic embedding for later retrieval via the AI Platform.",
      parameters: createMemoryStoreSchema(),
      async execute(_toolCallId, params) {
        const result = await callTool("tool_memory_store", params);
        return jsonResult(result);
      },
    });

    api.registerTool({
      name: "platform_memory_search",
      label: "Search Memory",
      description:
        "Search memories by semantic similarity using vector search in the AI Platform.",
      parameters: createMemorySearchSchema(),
      async execute(_toolCallId, params) {
        const result = await callTool("tool_memory_search", params);
        return jsonResult(result);
      },
    });

    api.registerTool({
      name: "platform_memory_store_structured",
      label: "Store Structured Memory",
      description:
        "Store a structured key-value fact (no embedding needed) in the AI Platform.",
      parameters: createStructuredStoreSchema(),
      async execute(_toolCallId, params) {
        const result = await callTool("tool_memory_store_structured", params);
        return jsonResult(result);
      },
    });

    api.registerTool({
      name: "platform_memory_get_structured",
      label: "Get Structured Memory",
      description:
        "Retrieve structured memories by key, category, or list all for an agent.",
      parameters: createStructuredGetSchema(),
      async execute(_toolCallId, params) {
        const result = await callTool("tool_memory_get_structured", params);
        return jsonResult(result);
      },
    });

    api.registerTool({
      name: "platform_get_group_instructions",
      label: "Get Group Instructions",
      description:
        "Get per-group instructions and settings for a WhatsApp group.",
      parameters: createGroupInstructionsSchema(),
      async execute(_toolCallId, params) {
        const result = await callTool("tool_get_group_instructions", params);
        return jsonResult(result);
      },
    });

    api.registerTool({
      name: "platform_get_agent_config",
      label: "Get Agent Config",
      description: "Get agent configuration (name, system prompt, model).",
      parameters: createAgentConfigSchema(),
      async execute(_toolCallId, params) {
        const result = await callTool("tool_get_agent_config", params);
        return jsonResult(result);
      },
    });

    api.registerTool({
      name: "platform_list_configured_groups",
      label: "List Configured Groups",
      description: "List all WhatsApp groups configured for an agent.",
      parameters: createListGroupsSchema(),
      async execute(_toolCallId, params) {
        const result = await callTool("tool_list_configured_groups", params);
        return jsonResult(result);
      },
    });
  },
};
