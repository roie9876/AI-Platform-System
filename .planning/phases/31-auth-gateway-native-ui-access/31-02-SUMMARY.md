---
phase: 31-auth-gateway-native-ui-access
plan: 02
subsystem: infra
tags: [kubernetes, deployment, ingress, cert-manager, network-policy, acr]

requires: []
provides:
  - Auth gateway K8s manifests (Deployment, Service, HPA, PDB, Ingress)
  - Conditional deployment in postprovision.sh
  - Wildcard certificate for agents subdomain
  - Tenant NetworkPolicy allowing auth-gateway ingress
affects: [auth-gateway, deployment, k8s]

tech-stack:
  added: []
  patterns: [conditional K8s deployment via AGENTS_DOMAIN, wildcard Ingress with AGC]

key-files:
  created:
    - k8s/base/auth-gateway/deployment.yaml
    - k8s/base/auth-gateway/service.yaml
    - k8s/base/auth-gateway/hpa.yaml
    - k8s/base/auth-gateway/pdb.yaml
    - k8s/base/auth-gateway/ingress-agents.yaml
  modified:
    - k8s/cert-manager/wildcard-certificate.yaml
    - k8s/overlays/tenant-template/network-policy.yaml
    - k8s/base/configmap.yaml
    - hooks/postprovision.sh

key-decisions:
  - "Auth-gateway NOT in kustomization.yaml — conditionally deployed via postprovision.sh"
  - "Wildcard cert moved to aiplatform namespace for Ingress TLS secret access"
  - "dnsNames updated to *.agents.{domain} pattern (agents subdomain prefix)"
  - "NetworkPolicy allows auth-gateway → tenant pods on ports 18789/18790"
  - "AGENTS_DOMAIN added to configmap template for both auth-gateway and frontend"

patterns-established:
  - "Conditional K8s deployment: manifests in k8s/base/ but deployed via postprovision.sh only when feature enabled"

requirements-completed: [NATIVEUI-01, NATIVEUI-02]

duration: 7min
completed: 2026-04-05
---

# Plan 31-02: Auth Gateway K8s Infrastructure Summary

**K8s Deployment, Service, HPA, PDB, wildcard Ingress, conditional deployment in postprovision.sh, certificate and NetworkPolicy updates for auth gateway.**

## Performance

- **Duration:** 7 min
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- Created 5 auth-gateway K8s manifests following token-proxy patterns
- Wildcard Ingress routes *.agents.{domain} and agents.{domain} to auth-gateway
- postprovision.sh builds auth-gateway Docker image (12 total images)
- Conditional auth-gateway deployment in Step 8.1 (only when AGENTS_DOMAIN set)
- Wildcard certificate moved to aiplatform namespace, dnsNames updated to agents.* prefix
- Tenant NetworkPolicy updated to allow auth-gateway cross-namespace access on ports 18789/18790
- AGENTS_DOMAIN added to configmap template

## Task Commits

1. **Task 1: Create K8s manifests** - `b72a1c4` (feat)
2. **Task 2: Update postprovision.sh, wildcard cert, network policy** - `b72a1c4` (feat)

## Files Created/Modified
- `k8s/base/auth-gateway/deployment.yaml` - Auth gateway Deployment spec (port 8000)
- `k8s/base/auth-gateway/service.yaml` - ClusterIP service on port 8000
- `k8s/base/auth-gateway/hpa.yaml` - HPA 2-5 replicas, 60% CPU
- `k8s/base/auth-gateway/pdb.yaml` - PDB minAvailable 1
- `k8s/base/auth-gateway/ingress-agents.yaml` - Wildcard Ingress for AGC
- `k8s/cert-manager/wildcard-certificate.yaml` - Moved to aiplatform ns, agents.* dnsNames
- `k8s/overlays/tenant-template/network-policy.yaml` - Auth-gateway ingress on 18789/18790
- `k8s/base/configmap.yaml` - Added AGENTS_DOMAIN field
- `hooks/postprovision.sh` - Auth-gateway build + conditional deployment
