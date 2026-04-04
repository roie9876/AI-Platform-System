# Phase 28: Infrastructure Audit & Foundation - Context

**Gathered:** 2026-04-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Make the entire AI Agent Platform deployable from zero via `azd up`. Audit all infrastructure artifacts (Bicep, K8s, cluster dependencies) by verifying they produce a working platform on a fresh Azure subscription. Add `azd` integration (`azure.yaml` + lifecycle hooks), conditional wildcard DNS/TLS with three domain options, Cosmos DB v4.0 containers, and fix K8s manifest gaps. The audit methodology is the `azd up` process itself — every drift surfaces as a deployment failure.

</domain>

<decisions>
## Implementation Decisions

### Audit Methodology
- **D-01:** No separate drift detection step. Running `azd up` from zero on a fresh subscription IS the audit — every missing resource, hardcoded value, or untracked dependency surfaces as a failure. Fix until it succeeds.

### Provision-from-Zero: `azd up`
- **D-02:** Use Azure Developer CLI (`azd`) for one-click deployment. Add `azure.yaml` at repo root declaring all services and lifecycle hooks.
- **D-03:** `azd` hooks install cluster dependencies that are currently "invisible" (not in repo): KEDA, OpenClaw operator, cert-manager (conditional), CSI Secrets Store driver. These become tracked in the repo via hook scripts and/or Helm values files.
- **D-04:** Target experience: `git clone → azd up → working platform`. No GitHub Copilot or Azure expertise required from the deploying user.

### Domain & TLS: Three-Option Model
- **D-05:** Three domain options controlled by `azd` environment parameters:
  - **Default (no domain):** AGC managed FQDN, free, zero manual steps. Platform UI + API + token proxy + MCP servers work. Native OpenClaw UI is NOT available.
  - **Buy via Azure (`AGENTS_DOMAIN` + `BUY_DOMAIN=true`):** App Service Domains (`Microsoft.DomainRegistration/domains`) purchases domain, auto-creates Azure DNS zone, NS delegation is automatic. cert-manager + Let's Encrypt DNS-01 issues wildcard cert. Fully automated, ~$12/year. ICANN contact info required as `azd` parameters.
  - **Bring your own (`AGENTS_DOMAIN` only):** Azure DNS zone created, cert-manager installed. User must manually add NS records at their registrar. `azd up` prints the NS records to add.
- **D-06:** Native OpenClaw UI (Phase 31) only available when `AGENTS_DOMAIN` is configured. Platform UI's "Open Agent Console" button conditionally rendered.
- **D-07:** cert-manager only installed when `AGENTS_DOMAIN` is set. Default deployments have no cert-manager overhead.

### Cosmos DB v4.0 Additions
- **D-08:** Add `token_logs` container to `cosmos.bicep` now (partition key `/tenant_id`, 90-day TTL). Consumed by Phase 29 (Token Proxy).
- **D-09:** Add DiskANN vector embedding policy to `agent_memories` container in `cosmos.bicep` now. Consumed by Phase 30 (MCP Servers).
- **D-10:** Both are just container/index definitions — no data migration, no application code.

### K8s Manifest Coverage
- **D-11:** Add `rbac-tenant-provisioner.yaml` to `k8s/base/kustomization.yaml` — it's a cluster bootstrap resource applied by `azd up`.
- **D-12:** OpenClaw CR (`openclawinstance.yaml`) stays OUT of kustomization — it's a per-tenant template applied dynamically by the platform API at tenant provision time.
- **D-13:** Tenant overlay resources (`k8s/overlays/tenant-template/`) stay as templates — applied dynamically by the platform API.

### Key Vault Separation (Platform vs Tenant Secrets)
- **D-14:** Split into two vaults: platform vault (existing, `stumsft-aiplat-prod-kv`) for infra secrets (Cosmos endpoint, Entra IDs, Service Bus, App Insights) and new tenant vault (`stumsft-aiplat-prod-tenants-kv`) for tenant secrets (Telegram tokens, Gmail passwords, AI model keys).
- **D-15:** New `infra/modules/keyvault-tenants.bicep` creates the tenant vault with separate RBAC. `main.bicep` wires it alongside the existing vault.
- **D-16:** Backend adds `TENANT_KEY_VAULT_NAME` env var with fallback to `KEY_VAULT_NAME` for backward compatibility during migration.
- **D-17:** Per-tenant `SecretProviderClass` uses the tenant vault (`TENANT_KEY_VAULT_NAME`). Control-plane pods keep the existing platform vault mount.
- **D-18:** Migration is safe rollout: deploy tenant vault → add env var → update backend with fallback → copy secrets → switch → verify → cleanup old secrets.
- **D-19:** For `azd up` new deployments, both vaults are created from scratch — no migration needed. Separation is day-1 architecture.

### Agent's Discretion
- `azure.yaml` service declarations and hook structure
- Helm values files for KEDA, OpenClaw operator, cert-manager (chart versions, namespace)
- `azd` parameter naming and prompt text for domain options
- ICANN contact info parameter structure (which fields, defaults)
- cert-manager ClusterIssuer configuration (Let's Encrypt staging vs prod, DNS-01 solver details)
- DiskANN vector embedding dimensions and distance function for `agent_memories`
- `token_logs` container TTL implementation (Cosmos DB TTL policy vs application-level)
- Whether `servicebus.bicep` needs a compiled `.json` or removal of stale `.json` files

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Infrastructure
- `infra/main.bicep` — Orchestrator: VNet, Log Analytics, Identity, Cosmos, ACR, AKS, App Insights, Alerts, Service Bus, AGC, Key Vault, Workload Identity Federation
- `infra/modules/cosmos.bicep` — 34 containers, all `/tenant_id` partition, serverless. Add `token_logs` + DiskANN here.
- `infra/modules/keyvault.bicep` — Platform Key Vault with platform infra secrets. Keep as-is for control-plane.
- `infra/modules/agc.bicep` — Application Gateway for Containers (Traffic Controller + subnet association)
- `infra/parameters/prod.bicepparam` — Production parameters (Sweden Central, Standard_D4s_v5, K8s 1.33)

### Kubernetes
- `k8s/base/kustomization.yaml` — Resource list for `kubectl apply -k`. Add `rbac-tenant-provisioner.yaml` here.
- `k8s/base/ingress.yaml` — Single AGC Ingress with path-based routing (api-gateway, agent-executor, workflow-engine, tool-executor, mcp-proxy, frontend)
- `k8s/base/configmap.yaml` — Platform config (COSMOS_DATABASE, service URLs, CORS origins)
- `k8s/base/secrets/secret-provider-class.yaml` — CSI Secrets Store: Key Vault → K8s Secret mapping
- `k8s/base/openclaw/openclawinstance.yaml` — OpenClaw CR template (per-tenant, NOT in kustomization)
- `k8s/base/rbac-tenant-provisioner.yaml` — ClusterRole for tenant namespace management

### Research
- `.planning/research/SUMMARY.md` — Synthesized v4.0 research findings
- `.planning/research/OPENCLAW-MCP-NATIVE-UI.md` — Wildcard DNS/TLS options, AGC behavior
- `.planning/research/AUTH-GATEWAY.md` — DNS zone Bicep, cert-manager ClusterIssuer examples

### Scripts
- `k8s/scripts/smoke-test.sh` — Post-deploy health checks (namespace defaults to `default`, should be `aiplatform`)
- `k8s/scripts/setup-tenant.sh` — Tenant provisioning script
- `scripts/deploy.sh` — Current manual deploy script (will be superseded by `azd up`)

### Requirements
- `.planning/REQUIREMENTS.md` §Infrastructure Audit — AUDIT-01 through AUDIT-06

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `infra/main.bicep` + all modules — complete Bicep stack, well-structured in deployment waves
- `k8s/base/` — full kustomize base with all microservice deployments/services
- `k8s/scripts/smoke-test.sh` — post-deploy validation (needs namespace fix)
- `scripts/deploy.sh` — current deployment logic that `azd` hooks can reference

### Known Issues to Fix
- `infra/modules/servicebus.bicep` has no compiled `.json` (drift signal — all other modules have both `.bicep` and `.json`)
- `k8s/scripts/smoke-test.sh` defaults namespace to `default` instead of `aiplatform`
- `k8s/base/configmap.yaml` hardcodes AGC FQDN in CORS alongside custom domain — needs parameterization
- `k8s/base/kustomization.yaml` missing `rbac-tenant-provisioner.yaml`
- No `azure.yaml` exists — must be created from scratch
- No cluster dependency tracking — KEDA, OpenClaw operator, cert-manager, CSI driver installs are unrecorded
- Single Key Vault stores both platform infra secrets and tenant secrets — security blast radius concern
- Per-tenant `SecretProviderClass` references platform vault `keyvaultName` — should reference tenant vault

### Established Patterns
- Bicep: flat module structure (`infra/modules/{resource}.bicep`), parameterized via `.bicepparam`
- K8s: kustomize base + dynamic overlays for tenants
- All containers use workload identity (`azure.workload.identity/use: "true"`)
- Key Vault → CSI Secrets Store → K8s Secret → env var chain for secrets

### Integration Points
- Phase 29 (Token Proxy) depends on `token_logs` Cosmos DB container provisioned here
- Phase 30 (MCP Servers) depends on DiskANN vector index on `agent_memories` provisioned here
- Phase 31 (Auth Gateway) depends on wildcard DNS/TLS conditionally provisioned here
- All subsequent phases depend on `azd up` working reliably

</code_context>
