---
phase: 29-token-proxy
plan: 02
subsystem: infra
tags: [kubernetes, deployment, hpa, pdb, kustomize]

requires:
  - phase: 29-token-proxy
    provides: Dockerfile for llm-proxy container
provides:
  - K8s Deployment (2 replicas, port 8080, workload identity)
  - ClusterIP Service at token-proxy.aiplatform.svc:8080
  - HPA (2-5 replicas, 60% CPU target)
  - PDB (minAvailable 1)
affects: [deployment, k8s, openclaw-routing]

tech-stack:
  added: []
  patterns: [shared control plane service in aiplatform namespace]

key-files:
  created:
    - k8s/base/token-proxy/deployment.yaml
    - k8s/base/token-proxy/service.yaml
    - k8s/base/token-proxy/hpa.yaml
    - k8s/base/token-proxy/pdb.yaml
  modified:
    - k8s/base/kustomization.yaml

key-decisions:
  - "2 replicas minimum for HA"
  - "AZURE_OPENAI_BASE from aiplatform-secrets/AZURE_OPENAI_ENDPOINT"
  - "Same resource limits as api-gateway (100m/256Mi request, 500m/512Mi limit)"

patterns-established:
  - "Shared service pattern in aiplatform namespace with workload identity"

requirements-completed: [PROXY-01]

duration: 5min
completed: 2025-07-16
---

# Plan 29-02: K8s Manifests for Token Proxy

**K8s Deployment, Service, HPA, and PDB for the LLM token proxy in the aiplatform namespace.**

## Accomplishments
- Created Deployment with 2 replicas, port 8080, health probes, workload identity
- Created ClusterIP Service exposing token-proxy at port 8080
- Created HPA scaling 2-5 replicas at 60% CPU utilization
- Created PDB ensuring minAvailable 1 during disruptions
- Updated kustomization.yaml with all 4 token-proxy resources

## Task Commits

1. **Task 1: Deployment + Service** - `5cf3b3c` (feat)
2. **Task 2: HPA + PDB + kustomization** - `5cf3b3c` (feat)
