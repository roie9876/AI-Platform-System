---
phase: 29-token-proxy
plan: 01
subsystem: llm-proxy
tags: [fastapi, httpx, cosmos-db, azure-openai, streaming, token-tracking]

requires:
  - phase: 28-cosmos-token-logs
    provides: token_logs Cosmos container provisioned
provides:
  - LLM token proxy FastAPI service (main.py)
  - TokenLogRepository for Cosmos DB token logging
  - Dockerfile for llm-proxy container on port 8080
affects: [29-02, 29-03, deployment, openclaw]

tech-stack:
  added: [httpx]
  patterns: [stream_options.include_usage, async fire-and-forget logging, path-based tenant routing]

key-files:
  created:
    - backend/microservices/llm_proxy/main.py
    - backend/microservices/llm_proxy/__init__.py
    - backend/microservices/llm_proxy/Dockerfile
    - backend/app/repositories/token_log_repository.py
  modified: []

key-decisions:
  - "Port 8080 for proxy (not 8000 like other services)"
  - "stream_options.include_usage injection for streaming token tracking"
  - "Async fire-and-forget logging — proxy latency not affected by Cosmos writes"
  - "httpx.AsyncClient with 120s timeout for LLM streaming"

patterns-established:
  - "Path-based tenant/agent identification: /proxy/{tenant_id}/{agent_id}/..."
  - "SSE line parsing for usage extraction from streaming responses"
  - "Non-fatal logging — Cosmos write failures are logged but never fail the response"

requirements-completed: [PROXY-01, PROXY-02, PROXY-03]

duration: 8min
completed: 2025-07-16
---

# Plan 29-01: Token Proxy Service Core

**FastAPI proxy service with streaming/non-streaming handlers and Cosmos DB token usage logging.**

## Accomplishments
- Created FastAPI proxy that transparently forwards LLM requests to Azure OpenAI
- Implemented streaming handler with `stream_options.include_usage` injection for token counting
- Created TokenLogRepository extending CosmosRepository base for token_logs container
- Built Dockerfile following mcp_proxy pattern but on port 8080

## Task Commits

1. **Task 1: TokenLogRepository + proxy service core** - `5cf3b3c` (feat)
2. **Task 2: Dockerfile** - `5cf3b3c` (feat)
