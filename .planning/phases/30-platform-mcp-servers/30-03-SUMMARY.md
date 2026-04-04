---
phase: 30-platform-mcp-servers
plan: 03
subsystem: infra
tags: [bicep, cosmos-db, docker, kubernetes, kustomize, openclaw]

requires:
  - phase: 30-01
    provides: MCP server code + module structure
  - phase: 30-02
    provides: Platform config tools in main.py
provides:
  - Cosmos containers memory_query_cache (1h TTL) and structured_memories
  - Dockerfile.mcp-platform-tools for linux/amd64 build
  - K8s Deployment (port 8085, workload identity), Service (ClusterIP), HPA (2-5 replicas)
  - Auto-injection of platform MCP server URL into every OpenClaw agent CR
affects: [deployment, openclaw-agents]

tech-stack:
  added: []
  patterns: [K8s manifest templating from token-proxy pattern, Cosmos TTL containers]

key-files:
  created:
    - backend/Dockerfile.mcp-platform-tools
    - k8s/base/mcp-platform-tools/deployment.yaml
    - k8s/base/mcp-platform-tools/service.yaml
    - k8s/base/mcp-platform-tools/hpa.yaml
  modified:
    - infra/modules/cosmos.bicep
    - k8s/base/kustomization.yaml
    - backend/app/services/openclaw_service.py

key-decisions:
  - "Platform MCP tools URL always injected AFTER user-configured URLs — cannot be overridden"
  - "AZURE_API_KEY env var from secretKeyRef AZURE_OPENAI_KEY — same pattern as token-proxy"
  - "memory_query_cache has 1h TTL for embedding cache (future cross-pod enhancement)"

patterns-established:
  - "Platform-level MCP servers run in aiplatform namespace, auto-injected into all agent CRs"

requirements-completed: [MCPSRV-06, MCPSRV-07]

duration: 10min
completed: 2026-04-04
---

# Phase 30, Plan 03: Infrastructure, Deployment, and Integration Summary

**Cosmos Bicep containers, Dockerfile, K8s manifests, and OpenClaw CR auto-injection for MCP platform tools**

## What Was Built

- `cosmos.bicep`: Added `memory_query_cache` (1h TTL) and `structured_memories` containers
- `Dockerfile.mcp-platform-tools`: Python 3.12 slim, installs `mcp[cli]>=1.27.0`, exposes port 8085
- K8s manifests: Deployment (workload identity, CSI secrets, health probes), ClusterIP Service on 8085, HPA 2-5 replicas at 60% CPU
- `kustomization.yaml`: Added 3 new resource references
- `openclaw_service.py`: Platform MCP tools URL (`http://mcp-platform-tools.aiplatform.svc.cluster.local:8085/mcp`) auto-injected into every agent's CR mcpServers config

## Self-Check: PASSED

- [x] Cosmos Bicep has memory_query_cache and structured_memories containers
- [x] Dockerfile builds for MCP platform tools
- [x] K8s manifests: Deployment, Service, HPA
- [x] kustomization.yaml references all 3 manifests
- [x] openclaw_service.py injects platform-tools URL
