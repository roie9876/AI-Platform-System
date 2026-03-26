---
phase: 20-microservice-extraction-aks-deployment
plan: 03
subsystem: infra
tags: [kubernetes, kustomize, aks, multi-tenant, networking, autoscaling]

requires:
  - phase: 20-microservice-extraction-aks-deployment
    plan: 01
    provides: Microservice Dockerfiles and entry points

provides:
  - Kustomize base manifests for 5 microservices (deployment + service each)
  - NGINX Ingress with path-based routing to all microservices
  - Shared ConfigMap with inter-service URLs and Cosmos DB settings
  - Tenant namespace template with full isolation (NetworkPolicy, ResourceQuota, LimitRange)
  - HPA definitions for all 5 services with CPU/memory scaling
  - setup-tenant.sh script for automated tenant provisioning

affects: [22-ci-cd, production-deployment]

tech-stack:
  added: [kustomize, nginx-ingress-controller]
  patterns: [base-overlay-kustomize, namespace-per-tenant, network-policy-isolation]

key-files:
  created:
    - k8s/base/kustomization.yaml
    - k8s/base/configmap.yaml
    - k8s/base/ingress.yaml
    - k8s/base/api-gateway/deployment.yaml
    - k8s/base/api-gateway/service.yaml
    - k8s/base/agent-executor/deployment.yaml
    - k8s/base/agent-executor/service.yaml
    - k8s/base/workflow-engine/deployment.yaml
    - k8s/base/workflow-engine/service.yaml
    - k8s/base/tool-executor/deployment.yaml
    - k8s/base/tool-executor/service.yaml
    - k8s/base/mcp-proxy/deployment.yaml
    - k8s/base/mcp-proxy/service.yaml
    - k8s/overlays/tenant-template/kustomization.yaml
    - k8s/overlays/tenant-template/namespace.yaml
    - k8s/overlays/tenant-template/network-policy.yaml
    - k8s/overlays/tenant-template/resource-quota.yaml
    - k8s/overlays/tenant-template/limit-range.yaml
    - k8s/overlays/tenant-template/hpa.yaml
    - k8s/scripts/setup-tenant.sh

key-decisions:
  - "Base/overlay Kustomize pattern — base defines deployments, tenant overlay adds namespace + isolation"
  - "NGINX Ingress routes by path prefix — agent chat/threads to agent-executor, tools to tool-executor, etc."
  - "NetworkPolicy blocks cross-namespace traffic, allows ingress-nginx + intra-namespace + Azure HTTPS egress"
  - "ResourceQuota per tenant: 4/8 CPU, 8/16Gi memory, 20 pods max"
  - "api-gateway and agent-executor scale to 5 replicas, others to 3"
  - "setup-tenant.sh uses sed substitution of TENANT_NAMESPACE/TENANT_SLUG placeholders and kubectl apply -k"

patterns-established:
  - "K8s deployment pattern: 3 probes (liveness/readiness/startup), envFrom configmap, workload identity SA"
  - "Tenant isolation: namespace + NetworkPolicy + ResourceQuota + LimitRange + HPA per tenant"
  - "ACR image naming: stumsftaiplatformprodacr.azurecr.io/aiplatform-{service}:latest"
---

## Summary

Created complete Kubernetes manifests for AKS deployment using Kustomize base/overlay pattern. The base layer defines deployments and services for all 5 microservices with health probes, resource limits, workload identity, and shared configuration. The tenant overlay template provides namespace-level isolation with NetworkPolicy (blocks cross-tenant traffic), ResourceQuota, LimitRange, and HPA autoscaling. A provisioning script automates tenant namespace creation via placeholder substitution.

## Commits

- `586e00d` — feat(20-03): create K8s base manifests with kustomize, deployments, services, and ingress
- `73562f9` — feat(20-03): create tenant namespace template with isolation resources
