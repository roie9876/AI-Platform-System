# Plan 28-02 Summary: azd up Orchestration + K8s Manifest Drift Fixes

## Status: Complete

## Changes Made

### Task 1: azure.yaml + Lifecycle Hooks + Cluster Dependency Installer
- **Created** `azure.yaml`: azd project definition with hooks-only approach (no `services:` section), Bicep provider pointing to `infra/main`
- **Created** `hooks/preprovision.sh`: Validates prerequisites (az, kubectl, helm, jq, Azure login)
- **Created** `hooks/postprovision.sh`: Gets AKS credentials, installs cluster deps, creates aiplatform namespace, substitutes configmap variables (CORS_ORIGINS, KEY_VAULT_NAME, TENANT_KEY_VAULT_NAME), applies K8s manifests via `kubectl apply -k`, conditionally applies cert-manager resources when AGENTS_DOMAIN is set
- **Created** `hooks/postdeploy.sh`: Runs smoke tests via `smoke-test.sh aiplatform`
- **Created** `scripts/install-cluster-deps.sh`: Helm installs for CSI Secrets Store Driver, KEDA, OpenClaw operator, and conditional cert-manager (only when AGENTS_DOMAIN is set per D-07)

### Task 2: K8s Manifest Drift Fixes + cert-manager Resources
- **Modified** `k8s/base/kustomization.yaml`: Added `rbac-tenant-provisioner.yaml` to resources list
- **Modified** `k8s/base/configmap.yaml`: Parameterized CORS_ORIGINS (`${CORS_ORIGINS}` placeholder substituted at deploy time), added `TENANT_KEY_VAULT_NAME` entry
- **Modified** `k8s/scripts/smoke-test.sh`: Changed default namespace from `"default"` to `"aiplatform"`
- **Created** `k8s/cert-manager/clusterissuer.yaml`: Let's Encrypt ClusterIssuer with DNS-01 solver via Azure DNS
- **Created** `k8s/cert-manager/wildcard-certificate.yaml`: Wildcard TLS certificate for `*.${AGENTS_DOMAIN}`

## Verification
- azure.yaml structure validated (correct hooks, no services section)
- All hook scripts executable (chmod +x verified)
- grep checks passed for all required patterns
- K8s manifest drift items resolved

## Requirements Covered
- AUDIT-01: azd up framework enables provision-from-zero
- AUDIT-03: K8s manifests match production (rbac-tenant-provisioner included, CORS parameterized)
- AUDIT-04: Cluster dependencies tracked in repo (install-cluster-deps.sh)
