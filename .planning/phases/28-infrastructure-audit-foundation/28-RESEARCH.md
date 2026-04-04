# Phase 28: Infrastructure Audit & Foundation - Research

**Researched:** 2026-04-04
**Domain:** Azure infrastructure provisioning (Bicep, AKS/K8s, azd, DNS/TLS, Cosmos DB, Key Vault)
**Confidence:** HIGH

## Summary

Phase 28 is an infrastructure-only phase with no application code changes. It validates that all infrastructure artifacts (Bicep templates, K8s manifests, cluster dependencies) produce a working platform when deployed from zero, then extends the infrastructure with wildcard DNS/TLS, Cosmos DB v4.0 containers, and Key Vault separation. The audit methodology is the `azd up` process itself — every gap surfaces as a deployment failure.

The primary technical challenge is creating the `azure.yaml` orchestration file and lifecycle hooks that install "invisible" cluster dependencies (KEDA, OpenClaw operator, cert-manager, CSI Secrets Store driver) which currently exist on the cluster but are not tracked in the repo. The three-option domain model (no domain / buy via Azure / bring your own) adds conditional complexity to Bicep and hooks but follows well-documented patterns. Key Vault separation is straightforward Bicep + backend env var work with a backward-compatible fallback.

**Primary recommendation:** Start with `azure.yaml` + hooks that perform `az deployment group create` → install cluster deps → `kubectl apply -k` → smoke test. Fix every failure until `azd up` succeeds on a fresh subscription. Then layer on DNS/TLS, Cosmos DB containers, and Key Vault separation.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** No separate drift detection step. Running `azd up` from zero on a fresh subscription IS the audit — every missing resource, hardcoded value, or untracked dependency surfaces as a failure. Fix until it succeeds.
- **D-02:** Use Azure Developer CLI (`azd`) for one-click deployment. Add `azure.yaml` at repo root declaring all services and lifecycle hooks.
- **D-03:** `azd` hooks install cluster dependencies that are currently "invisible" (not in repo): KEDA, OpenClaw operator, cert-manager (conditional), CSI Secrets Store driver.
- **D-04:** Target experience: `git clone → azd up → working platform`.
- **D-05:** Three domain options controlled by `azd` environment parameters: Default (AGC managed FQDN), Buy via Azure (App Service Domains), Bring your own (manual NS delegation).
- **D-06:** Native OpenClaw UI only available when `AGENTS_DOMAIN` is configured.
- **D-07:** cert-manager only installed when `AGENTS_DOMAIN` is set.
- **D-08:** Add `token_logs` container to `cosmos.bicep` (partition key `/tenant_id`, 90-day TTL).
- **D-09:** Add DiskANN vector embedding policy to `agent_memories` container in `cosmos.bicep`.
- **D-10:** Both are just container/index definitions — no data migration, no application code.
- **D-11:** Add `rbac-tenant-provisioner.yaml` to `k8s/base/kustomization.yaml`.
- **D-12:** OpenClaw CR stays OUT of kustomization — per-tenant template applied dynamically.
- **D-13:** Tenant overlay resources stay as templates — applied dynamically by platform API.
- **D-14:** Split into two vaults: platform vault (existing) and new tenant vault.
- **D-15:** New `infra/modules/keyvault-tenants.bicep` creates the tenant vault with separate RBAC.
- **D-16:** Backend adds `TENANT_KEY_VAULT_NAME` env var with fallback to `KEY_VAULT_NAME`.
- **D-17:** Per-tenant `SecretProviderClass` uses the tenant vault.
- **D-18:** Migration is safe rollout: deploy tenant vault → add env var → update backend with fallback → copy secrets → switch → verify → cleanup.
- **D-19:** For `azd up` new deployments, both vaults are created from scratch — no migration needed.

### Agent's Discretion
- `azure.yaml` service declarations and hook structure
- Helm values files for KEDA, OpenClaw operator, cert-manager (chart versions, namespace)
- `azd` parameter naming and prompt text for domain options
- ICANN contact info parameter structure
- cert-manager ClusterIssuer configuration (Let's Encrypt staging vs prod, DNS-01 solver details)
- DiskANN vector embedding dimensions and distance function for `agent_memories`
- `token_logs` container TTL implementation
- Whether `servicebus.bicep` needs a compiled `.json` or removal of stale `.json` files

### Deferred Ideas (OUT OF SCOPE)
None specified.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AUDIT-01 | User can run `az deployment` + `kubectl apply` from scratch and get a fully working platform identical to production | azure.yaml + hooks architecture, provision-from-zero workflow |
| AUDIT-02 | User can see Bicep template drift resolved — templates match all deployed Azure resources | azd up audit methodology, servicebus.bicep .json gap, Cosmos DB container additions |
| AUDIT-03 | User can see K8s manifest drift resolved — manifests match all running workloads, ConfigMaps, and Secrets | kustomization.yaml gap (rbac-tenant-provisioner.yaml), configmap parameterization, smoke-test namespace fix |
| AUDIT-04 | User can provision wildcard DNS record and TLS certificate for `*.agents.{domain}` | Three-option domain model, cert-manager DNS-01 with Azure DNS, conditional Bicep modules |
| AUDIT-05 | User can see platform secrets and tenant secrets in separate Key Vaults with independent RBAC | keyvault-tenants.bicep, TENANT_KEY_VAULT_NAME env var, RBAC isolation |
| AUDIT-06 | User can see existing tenant secrets migrated from platform vault to tenant vault with zero downtime | Safe rollout migration script, backward-compatible fallback pattern |
</phase_requirements>

## Standard Stack

### Core

| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| Azure Developer CLI (`azd`) | 1.16.1 | One-click deployment orchestration | Verified installed locally. Supports AKS host type, Bicep infra provider, lifecycle hooks |
| Azure CLI (`az`) | 2.84.0 | Azure resource provisioning, AKS credential management | Already in use via `scripts/deploy.sh` |
| Bicep CLI | 0.40.2 | Infrastructure as Code compilation | Already in use for all `infra/modules/` |
| Helm | 4.0.1 | Cluster dependency installation (KEDA, cert-manager, OpenClaw operator) | Standard K8s package manager; all three deps are Helm charts |
| kubectl | 1.30.5 | K8s manifest application, smoke testing | Already in use |
| cert-manager | 1.16+ (latest stable) | Wildcard TLS certificate via Let's Encrypt DNS-01 | De facto standard for K8s certificate management; official Azure DNS solver |

### Supporting

| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| jq | 1.7.1 | JSON parsing in hook scripts | Extracting deployment outputs from `az deployment group show` |
| Docker | 27.4.1 | Container image builds | Build and push microservice images (already in deploy.sh) |
| kustomize (via kubectl) | built-in | K8s manifest rendering | `kubectl apply -k k8s/base/` already used |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `azd` | Raw `scripts/deploy.sh` | deploy.sh already exists and works, but doesn't provide `azd env` parameter management, interactive prompts, or composable hooks. azd is the user decision (D-02). |
| Helm for all K8s manifests | Keep kustomize for platform, Helm only for deps | Converting existing manifests to Helm charts is out of scope; kustomize works fine for platform resources. |
| cert-manager DNS-01 | HTTP-01 challenge | HTTP-01 cannot issue wildcard certificates. DNS-01 is required for `*.agents.{domain}`. |

### Helm Charts to Install

| Chart | Repository | Purpose | Namespace |
|-------|-----------|---------|-----------|
| `kedacore/keda` | `https://kedacore.github.io/charts` | KEDA autoscaler for Service Bus queue triggers | `keda` |
| `jetstack/cert-manager` | `https://charts.jetstack.io` | Certificate management (conditional on `AGENTS_DOMAIN`) | `cert-manager` |
| `secrets-store-csi-driver/secrets-store-csi-driver` | `https://kubernetes-sigs.github.io/secrets-store-csi-driver/charts` | CSI Secrets Store driver for Key Vault → K8s Secret | `kube-system` |
| `csi-secrets-store-provider-azure` | `https://azure.github.io/secrets-store-csi-driver-provider-azure/charts` | Azure provider for CSI driver | `kube-system` |
| OpenClaw operator | `registry.openclaw.rocks/charts/openclaw-operator` (OCI) | OpenClaw CRD + operator for agent management | `openclaw-system` |

**Note:** Exact chart versions should be pinned in hook scripts. Verify latest stable versions at execution time.

## Architecture Patterns

### Recommended Project Structure

```
azure.yaml                              # NEW: azd project definition
hooks/                                  # NEW: azd lifecycle hook scripts
├── preprovision.sh                     # Validate prerequisites
├── postprovision.sh                    # Install cluster deps, apply K8s manifests
├── predeploy.sh                        # Build and push Docker images
└── postdeploy.sh                       # Smoke tests, default tenant setup
infra/
├── main.bicep                          # Existing: orchestrator (add DNS zone, tenant KV params)
├── modules/
│   ├── cosmos.bicep                    # MODIFY: add token_logs + DiskANN on agent_memories
│   ├── keyvault.bicep                  # KEEP: platform vault (unchanged)
│   ├── keyvault-tenants.bicep          # NEW: tenant secrets vault
│   ├── dns.bicep                       # NEW: conditional Azure DNS zone
│   ├── domain.bicep                    # NEW: conditional App Service Domain purchase
│   └── servicebus.bicep               # EXISTING: compile .json to fix drift
├── parameters/
│   └── prod.bicepparam                 # MODIFY: add new params
k8s/
├── base/
│   ├── kustomization.yaml             # MODIFY: add rbac-tenant-provisioner.yaml
│   ├── configmap.yaml                 # MODIFY: parameterize CORS_ORIGINS
│   └── secrets/
│       └── secret-provider-class.yaml # KEEP (platform vault ref)
├── cert-manager/                       # NEW: conditional cert-manager resources
│   ├── clusterissuer.yaml             # Let's Encrypt ClusterIssuer with Azure DNS solver
│   └── wildcard-certificate.yaml      # Certificate for *.agents.{domain}
scripts/
├── install-cluster-deps.sh            # NEW: Helm install KEDA, CSI, OpenClaw, cert-manager
├── migrate-tenant-secrets.sh          # NEW: Copy secrets from platform KV to tenant KV
k8s/scripts/
└── smoke-test.sh                      # MODIFY: fix default namespace → aiplatform
```

### Pattern 1: `azure.yaml` Structure for AKS

**What:** azd project definition with AKS host type and lifecycle hooks
**When to use:** Always — this is the core `azd up` orchestration

```yaml
# azure.yaml
name: ai-agent-platform
metadata:
  template: ai-agent-platform@4.0.0

infra:
  provider: bicep
  path: infra
  module: main

hooks:
  preprovision:
    posix:
      shell: sh
      run: ./hooks/preprovision.sh
      interactive: true
  postprovision:
    posix:
      shell: sh
      run: ./hooks/postprovision.sh
      interactive: true
  postdeploy:
    posix:
      shell: sh
      run: ./hooks/postdeploy.sh
      interactive: true

services:
  api-gateway:
    project: ./backend
    host: aks
    language: python
    docker:
      path: ./backend/Dockerfile
      context: ./backend
      platform: amd64
    k8s:
      deploymentPath: k8s/base/api-gateway
      namespace: aiplatform
  # ... (one service per microservice)
```

**Key insight:** `azd` with AKS host type uses `kubectl apply` on the `deploymentPath` manifests. The existing kustomize base works if `hooks/postprovision.sh` does `kubectl apply -k k8s/base/` after cluster dep installation.

**Alternative architecture:** Use hooks to run `kubectl apply -k` directly and skip per-service `k8s` declarations entirely, since the platform already uses kustomize. This is simpler:

```yaml
# Simpler approach: hooks-driven
name: ai-agent-platform
infra:
  provider: bicep
  path: infra
  module: main

hooks:
  postprovision:
    posix:
      shell: sh
      run: ./hooks/postprovision.sh
      interactive: true

# No services: section — hooks handle everything
```

**Recommendation:** The hooks-driven approach is more natural for this project since it already has kustomize-based deployment. azd's AKS service declarations are designed for simpler projects. Use hooks for the full deploy pipeline.

### Pattern 2: Conditional Bicep Modules (Three-Option Domain)

**What:** Domain and TLS resources conditionally deployed based on `azd` parameters
**When to use:** Implementing D-05 three-option domain model

```bicep
// main.bicep additions
@description('Custom domain for agent subdomains (e.g., agents.stumsft.com). Leave empty for AGC-managed FQDN.')
param agentsDomain string = ''

@description('Whether to purchase the domain via App Service Domains')
param buyDomain bool = false

// Conditional DNS zone — created when agentsDomain is set
module dnsZone './modules/dns.bicep' = if (!empty(agentsDomain)) {
  name: 'dns-deployment'
  params: {
    domainName: agentsDomain
    tags: commonTags
  }
}

// Conditional domain purchase — only when buyDomain is true
module domain './modules/domain.bicep' = if (buyDomain) {
  name: 'domain-deployment'
  params: {
    domainName: agentsDomain
    // ICANN contact params...
    tags: commonTags
  }
}
```

### Pattern 3: cert-manager Workload Identity Authentication

**What:** cert-manager authenticates to Azure DNS via Workload Identity Federation
**When to use:** DNS-01 challenge for wildcard TLS certificate
**Source:** cert-manager.io official docs, verified 2026-04-04

```yaml
# ClusterIssuer with Azure DNS solver
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@stumsft.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - dns01:
        azureDNS:
          hostedZoneName: "${AGENTS_DOMAIN}"
          resourceGroupName: "${RESOURCE_GROUP}"
          subscriptionID: "${AZURE_SUBSCRIPTION_ID}"
          environment: AzurePublicCloud
          managedIdentity:
            clientID: "${CERT_MANAGER_IDENTITY_CLIENT_ID}"
```

**Requirements:**
- Dedicated managed identity for cert-manager (or reuse platform workload identity with DNS Zone Contributor role added)
- Federated credential linking cert-manager ServiceAccount to the managed identity
- cert-manager Helm install with `podLabels: { azure.workload.identity/use: "true" }`

### Pattern 4: Cosmos DB Container with Vector Embedding + TTL (Bicep)

**What:** Declaring `token_logs` container with TTL and `agent_memories` with DiskANN
**When to use:** Extending cosmos.bicep for v4.0

```bicep
// token_logs container — 90-day TTL, partition by tenant_id
resource tokenLogsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: database
  name: 'token_logs'
  properties: {
    resource: {
      id: 'token_logs'
      partitionKey: {
        paths: ['/tenant_id']
        kind: 'Hash'
      }
      defaultTtl: 7776000  // 90 days in seconds
    }
  }
}

// agent_memories container — with DiskANN vector embedding policy
// NOTE: Separate resource because it needs vectorEmbeddingPolicy + indexingPolicy
resource agentMemoriesContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: database
  name: 'agent_memories'
  properties: {
    resource: {
      id: 'agent_memories'
      partitionKey: {
        paths: ['/tenant_id']
        kind: 'Hash'
      }
      vectorEmbeddingPolicy: {
        vectorEmbeddings: [
          {
            path: '/embedding'
            dataType: 'float32'
            dimensions: 1536        // text-embedding-3-small default
            distanceFunction: 'cosine'
          }
        ]
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        automatic: true
        includedPaths: [{ path: '/*' }]
        excludedPaths: [
          { path: '/_etag/?' }
          { path: '/embedding/*' }
        ]
        vectorIndexes: [
          {
            path: '/embedding'
            type: 'diskANN'
          }
        ]
      }
    }
  }
}
```

**Critical note:** `agent_memories` currently exists in the `containerNames` array (created with no special policy). The `vectorEmbeddingPolicy` and `vectorIndexes` may fail if the container already exists without them — Cosmos DB docs say you **cannot change settings directly, you must drop and re-add**. However, Bicep deployment is declarative — it may succeed if the API treats this as an additive change. **Must test on the actual account before planning assumes it works.**

**Dimensions:** 1536 is the default for `text-embedding-3-small` (the most common Azure OpenAI embedding model). This matches the model referenced in the research summary. Can be updated later if using a different model.

### Anti-Patterns to Avoid

- **Hardcoded resource names in hooks:** Use `azd env get-values` to read deployment outputs, not hardcoded `stumsft-aiplatform-prod-*` names
- **Running `azd provision` and `azd deploy` manually:** Use `azd up` which runs the full workflow (provision → deploy → hooks)
- **Installing cluster deps inside Bicep:** KEDA/cert-manager/CSI are K8s resources, not Azure resources. They belong in `postprovision` hooks, not Bicep
- **Single large hook script:** Split into focused scripts (install-deps, apply-manifests, smoke-test) called from hooks
- **Skipping Let's Encrypt staging:** Use staging endpoint for development/testing, production endpoint only when DNS is verified working

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| TLS certificate provisioning | Custom ACME client | cert-manager + ClusterIssuer | cert-manager handles renewal, secret rotation, DNS-01 challenges natively |
| DNS zone management | `az network dns` calls in scripts | Bicep `Microsoft.Network/dnsZones` | Declarative, idempotent, tracked as IaC |
| Domain purchase automation | Custom Azure SDK calls | Bicep `Microsoft.DomainRegistration/domains` (App Service Domains) | Native ARM resource, auto-delegates NS to Azure DNS zone |
| K8s secret sync from Key Vault | Custom sidecar / init container | CSI Secrets Store driver + Azure provider | Industry standard, handles rotation, already in use |
| KEDA scaling | Custom HPA + queue polling | KEDA ScaledObject with Service Bus trigger | Already in use for `agent-executor`, just needs Helm-tracked install |
| Compiled Bicep JSON | Manual `az bicep build` in CI | Don't compile — Bicep CLI in az deployment handles it | `.json` files are stale copies. Either re-compile or remove old ones. Recommendation: remove `.json` files, rely on Bicep CLI directly. |

## Common Pitfalls

### Pitfall 1: `vectorEmbeddingPolicy` on Existing Container
**What goes wrong:** Deploying Bicep with `vectorEmbeddingPolicy` on the existing `agent_memories` container may fail because the policy was not set at creation time.
**Why it happens:** Cosmos DB documentation states: "You can add new path configurations or remove existing ones, but you cannot change the settings of a vector embedding policy." Some operations may require drop + recreate.
**How to avoid:** Test the Bicep deployment against the existing production Cosmos DB account first. If it fails, plan includes a manual migration step: create `agent_memories_v2` with the policy, copy data, swap queries, delete old container.
**Warning signs:** `az deployment group create` returns error about immutable policy or unsupported operation on existing container.

### Pitfall 2: cert-manager Identity Federation
**What goes wrong:** cert-manager pods can't authenticate to Azure DNS because federated credentials aren't set up correctly.
**Why it happens:** cert-manager uses its own ServiceAccount (`cert-manager` in `cert-manager` namespace), which needs its own federated credential — it cannot share the platform workload identity federation without binding to the same service account.
**How to avoid:** Either (a) create a dedicated managed identity for cert-manager with its own federated credential, or (b) reuse the platform workload identity but add a second federated credential for `system:serviceaccount:cert-manager:cert-manager`. Option (a) is cleaner — add it to `identity.bicep`.
**Warning signs:** `ClusterIssuer` shows `ClientID was omitted without providing one of --cluster-issuer-ambient-credentials` or similar RBAC errors.

### Pitfall 3: azd Parameter vs Environment Variable Confusion
**What goes wrong:** Parameters defined in `main.bicep` are not automatically available as `azd` environment variables in hooks.
**Why it happens:** `azd` stores its own environment variables in `.azure/{env}/.env`. Bicep outputs are injected as `azd` env vars after provisioning. But Bicep *params* are not — they come from `.bicepparam` files.
**How to avoid:** Design the flow so `azd env set AGENTS_DOMAIN "..."` stores domain in `.env`, then `main.bicep` reads it as a parameter via `azd provision`, and hooks also read it via `azd env get-values`. Bicep params should come from `azd` env, not hardcoded `.bicepparam` files.
**Warning signs:** Hooks can't find values that were set as Bicep parameters but never exported.

### Pitfall 4: Smoke Test Namespace Default
**What goes wrong:** `k8s/scripts/smoke-test.sh` defaults to `NAMESPACE="default"` but all platform resources are in `aiplatform`.
**Why it happens:** Original script was written before namespace convention was established.
**How to avoid:** Change default to `NAMESPACE="aiplatform"`. This is a known issue documented in CONTEXT.md.
**Warning signs:** Smoke test passes but checks the wrong namespace.

### Pitfall 5: AGC Frontend FQDN Hardcoding
**What goes wrong:** `k8s/base/configmap.yaml` hardcodes the AGC FQDN (`c9f9gagpbsf9fpe7.fz71.alb.azure.com`) in CORS_ORIGINS.
**Why it happens:** AGC assigns a random FQDN that was manually copied into the configmap.
**How to avoid:** Parameterize CORS_ORIGINS in the configmap. The hook script should substitute the actual AGC FQDN from deployment outputs using `sed` or `envsubst`.
**Warning signs:** New deployments have wrong CORS origins, frontend can't reach API.

### Pitfall 6: Service Bus `.json` Drift
**What goes wrong:** `infra/modules/servicebus.bicep` exists but has no compiled `servicebus.json`, while all other modules have both `.bicep` and `.json`.
**Why it happens:** Service Bus module was added later without running `az bicep build`.
**How to avoid:** Decision required: either compile all `.json` files consistently, or remove all `.json` files and rely on Bicep CLI at deployment time. Recommendation: remove all `.json` files — they are stale artifacts that can drift from `.bicep` source.
**Warning signs:** Inconsistent module directory causes confusion about which files are authoritative.

### Pitfall 7: Key Vault Tenant Secret Migration Ordering
**What goes wrong:** Tenant pods crash because secrets are moved from platform vault before the pod's `SecretProviderClass` is updated to point to the tenant vault.
**Why it happens:** Migration steps executed out of order.
**How to avoid:** Follow D-18 ordering strictly: (1) deploy tenant vault via Bicep, (2) add `TENANT_KEY_VAULT_NAME` env var to control plane, (3) deploy backend with fallback code, (4) copy secrets to tenant vault, (5) update tenant `SecretProviderClass` to use tenant vault, (6) verify, (7) clean up old secrets from platform vault.
**Warning signs:** Tenant pods enter `CrashLoopBackOff` with `SecretNotFound` errors.

## Code Examples

### azd Hook: Post-Provision Cluster Dependency Installation

```bash
#!/bin/bash
set -euo pipefail

# hooks/postprovision.sh — Install cluster dependencies after Azure infra is provisioned

echo "Loading azd environment variables..."
while IFS='=' read -r key value; do
    value=$(echo "$value" | sed 's/^"//' | sed 's/"$//')
    export "$key=$value"
done <<EOF
$(azd env get-values)
EOF

# Get AKS credentials
az aks get-credentials \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --name "$AKS_CLUSTER_NAME" \
  --overwrite-existing

# Install cluster deps
./scripts/install-cluster-deps.sh

# Apply K8s manifests
kubectl apply -k k8s/base/ --namespace aiplatform

# Conditional: cert-manager resources
AGENTS_DOMAIN=$(azd env get-value AGENTS_DOMAIN 2>/dev/null || echo "")
if [ -n "$AGENTS_DOMAIN" ]; then
  echo "Agents domain configured: $AGENTS_DOMAIN"
  echo "Applying cert-manager ClusterIssuer and Certificate..."
  envsubst < k8s/cert-manager/clusterissuer.yaml | kubectl apply -f -
  envsubst < k8s/cert-manager/wildcard-certificate.yaml | kubectl apply -f -
fi
```

### Bicep: Tenant Key Vault Module

```bicep
// infra/modules/keyvault-tenants.bicep
@description('Azure region')
param location string

@description('Environment name')
param environmentName string = 'prod'

@description('Workload identity principal ID')
param workloadIdentityPrincipalId string

@description('Log Analytics workspace ID')
param logAnalyticsWorkspaceId string = ''

@description('Azure AD tenant ID')
param tenantId string = subscription().tenantId

@description('Tags')
param tags object = {}

// Name: stumsft-aiplat-prod-tenants-kv = 27 chars (max 24 — need to shorten)
// Shortened: stumsft-aiplat-prod-tkv = 23 chars
resource tenantVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: 'stumsft-aiplat-${environmentName}-tkv'
  location: location
  tags: tags
  properties: {
    sku: { family: 'A', name: 'standard' }
    tenantId: tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    publicNetworkAccess: 'Enabled'
  }
}

// Workload identity gets Secrets User on tenant vault
resource kvSecretsUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(tenantVault.id, workloadIdentityPrincipalId, '4633458b-17de-408a-b874-0445c86b69e6')
  scope: tenantVault
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '4633458b-17de-408a-b874-0445c86b69e6' // Key Vault Secrets User
    )
    principalId: workloadIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

output tenantKeyVaultName string = tenantVault.name
output tenantKeyVaultUri string = tenantVault.properties.vaultUri
```

**Key Vault name constraint:** Max 24 characters. Original name `stumsft-aiplat-prod-tenants-kv` (30 chars) is too long. Use `stumsft-aiplat-prod-tkv` (23 chars).

### Bicep: Conditional DNS Zone

```bicep
// infra/modules/dns.bicep
@description('Domain name for agent subdomains')
param domainName string

@description('Tags')
param tags object = {}

resource dnsZone 'Microsoft.Network/dnsZones@2023-07-01-preview' = {
  name: domainName
  location: 'global'
  tags: tags
}

// Wildcard A record pointing to AGC public IP (set by hook after AGC frontend resolves)
// Placeholder — actual IP set post-provisioning via az network dns record-set a add-record

output dnsZoneId string = dnsZone.id
output dnsZoneName string = dnsZone.name
output nameServers array = dnsZone.properties.nameServers
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `scripts/deploy.sh` manual orchestration | `azd up` with hooks | v4.0 (this phase) | One-command deployment, parameter management |
| Single Key Vault for all secrets | Platform + Tenant vault separation | v4.0 (this phase) | Better security blast radius, tenant isolation |
| Cluster deps installed manually (not tracked) | Helm install in tracked hook scripts | v4.0 (this phase) | Reproducible from-zero deployment |
| Compiled `.json` alongside `.bicep` | Bicep CLI at deploy time (or consistent compilation) | v4.0 (this phase) | Eliminates stale artifact drift |
| AAD Pod Identity for cert-manager | Workload Identity Federation | cert-manager v1.11+ | Pod Identity is deprecated; Workload Identity is recommended |

## Open Questions

1. **`agent_memories` Vector Policy Migration**
   - What we know: Cosmos DB docs say you can't change vector embedding policy settings on existing containers. ARM/Bicep deployment is declarative.
   - What's unclear: Whether deploying Bicep with `vectorEmbeddingPolicy` on a container that was created without one constitutes "adding" (allowed) or "changing" (blocked).
   - Recommendation: Test against production account in a dry-run (`az deployment group what-if`). If blocked, plan a container recreation step.

2. **cert-manager Identity Strategy**
   - What we know: cert-manager needs DNS Zone Contributor role on the Azure DNS zone. Platform workload identity exists and has federated credentials for `aiplatform` namespace.
   - What's unclear: Whether to create a dedicated managed identity for cert-manager or add a second federated credential to the existing workload identity.
   - Recommendation: Dedicated identity is cleaner (add `certManagerIdentity` to `identity.bicep`) and follows principle of least privilege. But reusing existing identity reduces module count.

3. **Compiled `.json` File Strategy**
   - What we know: All modules except `servicebus.bicep` have compiled `.json` siblings. `servicebus.json` is missing.
   - What's unclear: Whether these `.json` files are actively used by any process, or if they're stale artifacts.
   - Recommendation: Check `scripts/deploy.sh` — it uses `--template-file infra/main.bicep`, so `.json` files are unused. Remove them all to eliminate drift, or compile `servicebus.json` for consistency. Removing is preferred.

4. **azd AKS Services vs Hooks-Only Architecture**
   - What we know: azd supports `host: aks` per-service with `k8s.deploymentPath`. The project uses kustomize base with cross-service resources (configmap, ingress, RBAC).
   - What's unclear: Whether azd can handle the interdependencies of a kustomize-based deployment (shared configmap, namespace creation, RBAC) via per-service declarations.
   - Recommendation: Use hooks-only approach. Declare no `services:` section, handle all K8s deployment in `postprovision` hook. This matches the project's existing kustomize pattern.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Azure CLI | Bicep deployment, AKS auth | ✓ | 2.84.0 | — |
| Azure Developer CLI (azd) | One-click deployment | ✓ | 1.16.1 | — |
| Bicep CLI | IaC compilation | ✓ | 0.40.2 | — |
| kubectl | K8s manifest application | ✓ | 1.30.5 | — |
| Helm | Cluster dep installation | ✓ | 4.0.1 | — |
| Docker | Image builds | ✓ | 27.4.1 | — |
| jq | JSON parsing in hooks | ✓ | 1.7.1 | — |
| kustomize (standalone) | K8s rendering | ✗ | — | `kubectl apply -k` (built-in kustomize) |
| envsubst | Template variable substitution | needs check | — | `sed` replacement |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:**
- `kustomize` standalone not installed, but `kubectl apply -k` provides equivalent functionality (built-in).
- `envsubst` availability should be verified; `sed` can substitute if missing.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x (asyncio_mode=auto) |
| Config file | `backend/pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `cd backend && python -m pytest tests/ -x --timeout=30` |
| Full suite command | `cd backend && python -m pytest tests/ --timeout=60` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AUDIT-01 | Provision-from-zero produces working platform | e2e/smoke | `k8s/scripts/smoke-test.sh aiplatform --extended` | ✅ (needs namespace fix) |
| AUDIT-02 | Bicep templates match deployed resources | e2e | `az deployment group what-if --resource-group $RG --template-file infra/main.bicep --parameters infra/parameters/prod.bicepparam` | N/A (Azure CLI, not pytest) |
| AUDIT-03 | K8s manifests match running workloads | e2e | `kubectl diff -k k8s/base/ --namespace aiplatform` | N/A (kubectl, not pytest) |
| AUDIT-04 | Wildcard DNS resolves + TLS cert issued | e2e/smoke | `curl -s https://test.agents.${AGENTS_DOMAIN}/ -o /dev/null -w '%{http_code}'` + `kubectl get certificate -n cert-manager` | ❌ Wave 0 |
| AUDIT-05 | Platform and tenant secrets in separate vaults | unit | `python -m pytest tests/test_keyvault_separation.py -x` | ❌ Wave 0 |
| AUDIT-06 | Tenant secrets migrated with zero downtime | manual | Migration script execution + pod health check | N/A (operational, not automated test) |

### Sampling Rate
- **Per task commit:** `cd backend && python -m pytest tests/ -x --timeout=30`
- **Per wave merge:** Full pytest suite + smoke-test.sh
- **Phase gate:** `azd up` succeeds on test environment + smoke-test.sh passes + `kubectl diff` shows no drift

### Wave 0 Gaps
- [ ] `tests/test_keyvault_separation.py` — unit tests for TENANT_KEY_VAULT_NAME fallback logic (AUDIT-05)
- [ ] DNS/TLS validation script in `k8s/scripts/` or `hooks/` (AUDIT-04)
- [ ] Smoke test namespace fix must happen before any validation (AUDIT-01, AUDIT-03)

## Project Constraints (from copilot-instructions.md)

No `copilot-instructions.md` file found with actionable project-specific constraints for this phase. The general project constraints from PROJECT.md apply:
- **Tech Stack:** Python/FastAPI backend, React/Next.js frontend
- **Microsoft Products:** Use Microsoft services extensively
- **Multi-tenant:** Secure isolation between tenants
- Docker images must use `--platform linux/amd64` for AKS (from user memory)
- ACR: `stumsftaiplatformprodacr.azurecr.io`
- AKS cluster: `stumsft-aiplatform-prod-aks`, namespace: `aiplatform`

## Sources

### Primary (HIGH confidence)
- Azure Developer CLI schema: https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/azd-schema — azure.yaml format, AKS host properties, hooks
- Azure Developer CLI hooks: https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/azd-extensibility — lifecycle hooks, environment variables
- cert-manager Azure DNS: https://cert-manager.io/docs/configuration/acme/dns01/azuredns/ — Workload Identity auth, ClusterIssuer config
- Cosmos DB vector search: https://learn.microsoft.com/en-us/azure/cosmos-db/nosql/vector-search — container vector policies, DiskANN index, limitations
- Cosmos DB Bicep container API: https://learn.microsoft.com/en-us/azure/templates/microsoft.documentdb/databaseaccounts/sqldatabases/containers — vectorEmbeddingPolicy, vectorIndexes, defaultTtl
- Existing codebase: `infra/main.bicep`, `infra/modules/`, `k8s/base/`, `scripts/deploy.sh` — current infrastructure architecture
- `.planning/research/SUMMARY.md`, `AUTH-GATEWAY.md`, `OPENCLAW-MCP-NATIVE-UI.md` — v4.0 architecture research

### Secondary (MEDIUM confidence)
- azd version 1.16.1 — verified locally via `azd version`
- All tool versions verified locally via terminal commands

### Tertiary (LOW confidence)
- App Service Domains Bicep (`Microsoft.DomainRegistration/domains`) — referenced in CONTEXT.md D-05 but not verified with Bicep ARM template reference. ICANN contact parameter structure needs validation.
- OpenClaw operator Helm chart URL — assumed from convention, actual registry URL needs verification.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all tools verified locally, Bicep/K8s patterns are well-established in the codebase
- Architecture: HIGH — extends existing patterns (Bicep modules, kustomize base, hook scripts), azd schema verified from official docs
- Pitfalls: HIGH — identified from codebase inspection (known issues in CONTEXT.md) + official docs (Cosmos DB vector policy limitations, cert-manager identity requirements)
- Domain/TLS: MEDIUM — cert-manager DNS-01 is well-documented but AGC + wildcard Ingress interaction not yet tested on this specific deployment
- Cosmos DB DiskANN: MEDIUM — API supports it in Bicep but retroactive application to existing container is uncertain

**Research date:** 2026-04-04
**Valid until:** 2026-05-04 (30 days — stable infrastructure patterns)
