#!/usr/bin/env node
/**
 * mcp-http-bridge.mjs
 *
 * Bridges stdio MCP transport to Streamable HTTP MCP transport.
 * OpenClaw's acpx plugin only supports stdio-based MCP servers
 * (command+args+env). This script acts as a stdio MCP server and
 * forwards all JSON-RPC messages to our HTTP-based MCP server.
 *
 * Usage (via OpenClaw mcpServers config):
 *   command: "node"
 *   args: ["/app/mcp-http-bridge.mjs"]
 *   env: { MCP_URL: "http://mcp-platform-tools.aiplatform.svc.cluster.local:8085/mcp" }
 */

import { createInterface } from "node:readline";

const MCP_URL = process.env.MCP_URL;
if (!MCP_URL) {
  process.stderr.write("[mcp-http-bridge] MCP_URL environment variable is required\n");
  process.exit(1);
}

let sessionId;

const rl = createInterface({ input: process.stdin, terminal: false });

rl.on("line", async (line) => {
  if (!line.trim()) return;

  try {
    const headers = {
      "Content-Type": "application/json",
      Accept: "application/json, text/event-stream",
    };
    if (sessionId) {
      headers["Mcp-Session-Id"] = sessionId;
    }

    const res = await fetch(MCP_URL, {
      method: "POST",
      headers,
      body: line,
    });

    // Capture session ID from server
    const sid = res.headers.get("mcp-session-id");
    if (sid) sessionId = sid;

    const ct = res.headers.get("content-type") || "";

    if (res.status === 202) {
      // Notification accepted — no response body
      return;
    }

    if (ct.includes("text/event-stream")) {
      // Parse SSE response — extract JSON-RPC messages from data: lines
      const text = await res.text();
      for (const chunk of text.split("\n")) {
        if (chunk.startsWith("data: ")) {
          const data = chunk.slice(6).trim();
          if (data) {
            process.stdout.write(data + "\n");
          }
        }
      }
    } else if (ct.includes("application/json")) {
      const body = await res.text();
      if (body.trim()) {
        process.stdout.write(body.trim() + "\n");
      }
    }
  } catch (err) {
    // Return JSON-RPC error for requests (that have an id)
    try {
      const req = JSON.parse(line);
      if (req.id !== undefined) {
        const errResp = {
          jsonrpc: "2.0",
          id: req.id,
          error: {
            code: -32603,
            message: `MCP HTTP bridge error: ${err.message}`,
          },
        };
        process.stdout.write(JSON.stringify(errResp) + "\n");
      }
    } catch {
      // If we can't parse the original request, just log
    }
    process.stderr.write(`[mcp-http-bridge] ${err.message}\n`);
  }
});

rl.on("close", () => {
  process.exit(0);
});
