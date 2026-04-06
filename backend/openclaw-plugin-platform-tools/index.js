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

function createMemoryDeleteSchema() {
  return Type.Object(
    {
      tenant_id: Type.String({ description: "Tenant identifier" }),
      agent_id: Type.String({ description: "Agent identifier" }),
      memory_id: Type.String({ description: "ID of the memory to delete" }),
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
      name: "platform_memory_delete",
      label: "Delete Memory",
      description:
        "Delete a specific memory entry by its ID from the AI Platform.",
      parameters: createMemoryDeleteSchema(),
      async execute(_toolCallId, params) {
        const result = await callTool("tool_memory_delete", params);
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

    // -----------------------------------------------------------------------
    //  Auto-store: save every conversation turn to Cosmos DB
    // -----------------------------------------------------------------------

    const tenantId = process.env.PLATFORM_TENANT_ID || "";
    const agentId = process.env.PLATFORM_AGENT_ID || "";

    if (tenantId && agentId) {
      // After each agent turn, store user messages and assistant response
      api.on("agent_end", async (event) => {
        if (!event.success || !event.messages || event.messages.length === 0) return;
        try {
          const userTexts = [];
          let assistantText = "";

          for (const msg of event.messages) {
            if (!msg || typeof msg !== "object") continue;
            let content = typeof msg.content === "string"
              ? msg.content
              : Array.isArray(msg.content)
                ? msg.content
                    .filter((b) => b && b.type === "text" && b.text)
                    .map((b) => b.text)
                    .join("\n")
                : "";
            if (!content || content.length < 3) continue;

            // Strip recalled memories context to prevent feedback loop
            if (msg.role === "user") {
              const recallIdx = content.indexOf("## Recalled Memories\n");
              if (recallIdx !== -1) {
                const endMarker = "Use these memories to provide context-aware responses.\n";
                const endIdx = content.indexOf(endMarker, recallIdx);
                if (endIdx !== -1) {
                  content = content.slice(0, recallIdx) + content.slice(endIdx + endMarker.length);
                } else {
                  content = content.slice(0, recallIdx);
                }
                content = content.trim();
              }
              // Also strip OpenClaw conversation metadata JSON to keep memories clean
              const metaIdx = content.indexOf("Conversation info (untrusted metadata):");
              if (metaIdx !== -1) {
                content = content.slice(0, metaIdx).trim();
              }
              // Strip queued message wrappers
              if (content.startsWith("[Queued messages while agent was busy]")) {
                // Extract actual message text from queued messages
                const lines = content.split("\n");
                const msgLines = lines.filter(
                  (l) =>
                    l.trim() &&
                    !l.startsWith("[Queued") &&
                    !l.startsWith("---") &&
                    !l.startsWith("Queued #") &&
                    !l.startsWith("Conversation info") &&
                    !l.startsWith("Sender (") &&
                    !l.startsWith("```") &&
                    !l.startsWith("{") &&
                    !l.startsWith("}") &&
                    !l.startsWith('"')
                );
                content = msgLines.join("\n").trim();
              }
              if (content.length >= 3) userTexts.push(content);
            } else if (msg.role === "assistant") {
              assistantText = content;
            }
          }

          // Store user messages
          for (const text of userTexts.slice(0, 3)) {
            try {
              await callTool("tool_memory_store", {
                tenant_id: tenantId,
                agent_id: agentId,
                content: `User said: ${text}`,
                memory_type: "user_input",
                source: "auto-capture",
              });
            } catch (e) {
              api.logger?.warn?.(`platform-tools: auto-store user msg failed: ${e}`);
            }
          }

          // Store assistant response
          if (assistantText && assistantText.length > 10) {
            try {
              await callTool("tool_memory_store", {
                tenant_id: tenantId,
                agent_id: agentId,
                content: `Assistant replied: ${assistantText}`,
                memory_type: "assistant_response",
                source: "auto-capture",
              });
            } catch (e) {
              api.logger?.warn?.(`platform-tools: auto-store assistant msg failed: ${e}`);
            }
          }
        } catch (err) {
          api.logger?.warn?.(`platform-tools: agent_end auto-store error: ${err}`);
        }
      });

      // Before each agent turn, recall relevant memories and inject into context
      api.on("before_agent_start", async (event) => {
        if (!event.prompt || event.prompt.length < 5) return;
        try {
          const result = await callTool("tool_memory_search", {
            tenant_id: tenantId,
            agent_id: agentId,
            query: event.prompt,
            top_k: 5,
          });
          const parsed = result?.content?.[0]?.text
            ? JSON.parse(result.content[0].text)
            : null;
          if (!parsed?.results || parsed.results.length === 0) return;

          const memoryLines = parsed.results
            .filter((r) => r.similarity_score > 0.3)
            .map((r) => `- [${r.memory_type}] ${r.content} (${new Date(r.created_at).toLocaleDateString()})`)
            .join("\n");

          if (!memoryLines) return;
          api.logger?.info?.(`platform-tools: injecting ${parsed.results.length} recalled memories`);
          return {
            prependContext:
              "## Recalled Memories\n" +
              "The following are relevant memories from past conversations:\n\n" +
              memoryLines +
              "\n\nUse these memories to provide context-aware responses.\n",
          };
        } catch (err) {
          api.logger?.warn?.(`platform-tools: before_agent_start recall error: ${err}`);
        }
      });

      api.logger?.info?.(`platform-tools: auto-store and auto-recall enabled for agent ${agentId}`);
    } else {
      api.logger?.warn?.("platform-tools: PLATFORM_TENANT_ID or PLATFORM_AGENT_ID not set, auto-store/recall disabled");
    }
  },
};
