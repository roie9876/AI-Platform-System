# Phase 17: Infrastructure Foundation (Bicep IaC) - Context

**Gathered:** 2026-03-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Provision all Azure resources for the AI Agent Platform via Bicep modules — AKS, ACR, Cosmos DB, VNet + subnets, Managed Identities, Key Vault, and Log Analytics — controlled by a single orchestrator (`main.bicep`) with a production parameter file. Deployment is idempotent via `az deployment group create`.

</domain>

<decisions>
## Implementation Decisions

### Module Structure & Naming
- **D-01:** Bicep files live at `infra/` at repo root — `infra/main.bicep`, `infra/modules/`, `infra/parameters/`
- **D-02:** Flat module organization — one file per resource type: `infra/modules/aks.bicep`, `infra/modules/cosmos.bicep`, `infra/modules/vnet.bicep`, `infra/modules/acr.bicep`, `infra/modules/keyvault.bicep`, `infra/modules/identity.bicep`, `infra/modules/loganalytics.bicep`
- **D-03:** Environment parameters use `.bicepparam` files (Bicep-native, type-safe)
- **D-04:** Azure resource naming convention: `stumsft-aiplatform-{env}-{resource}` — e.g., `stumsft-aiplatform-prod-aks`, `stumsft-aiplatform-prod-cosmos`

### Networking Topology
- **D-05:** Single VNet with 3 subnets: `aks-nodes`, `aks-pods` (Azure CNI Overlay), `private-endpoints`
- **D-06:** All resources use public access — no private endpoints. Simplicity over enterprise lockdown.

### Cosmos DB Container Design
- **D-07:** All containers pre-created in Phase 17 matching the 13+ existing SQLAlchemy models — ready for Phase 19 data migration
- **D-08:** Serverless throughput mode — pay-per-request, no minimum cost, ideal for internal platform with 2-5 tenants

### Environment Parameterization
- **D-09:** Single production environment only — no dev/staging. One `.bicepparam` file: `prod.bicepparam`
- **D-10:** Single resource group with environment tags (e.g., `rg-aiplatform`) — simpler lifecycle for one environment
- **D-11:** AKS production sizing: 3 nodes Standard_D4s_v5 (system + user node pools)

### Agent's Discretion
- NSG rule specifics within the VNet subnets
- Cosmos DB container unique key constraints (mapped from existing SQLAlchemy unique constraints)
- Key Vault access policy details (RBAC vs access policies)
- Log Analytics workspace SKU and retention period
- Managed Identity naming and role assignment specifics
- ACR SKU selection (Basic/Standard/Premium)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture
- `docs/architecture/HLD-ARCHITECTURE.md` — Defines the target Azure topology (AKS, ACR, Cosmos DB, Key Vault, VNet), deployment architecture, and Microsoft product mapping

### Requirements
- `.planning/REQUIREMENTS.md` §Infrastructure Provisioning — INFRA-01 through INFRA-09 define all resource provisioning requirements

### Existing Infrastructure
- `docker-compose.yml` — Current local dev setup (PostgreSQL, Redis, backend, frontend) — reference for understanding service topology being replaced
- `backend/Dockerfile` — Python 3.12 backend container spec
- `frontend/Dockerfile` — Node 20 frontend container spec

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `docker-compose.yml`: Defines current service topology (backend, frontend, db, redis) — informs container mapping for AKS
- `backend/Dockerfile`: Python 3.12-slim base image — same base for microservice containers in Phase 20
- `frontend/Dockerfile`: Node 20-alpine base — same base for frontend container

### Established Patterns
- SQLAlchemy models in `backend/app/models/` define the 13+ data models that map to Cosmos DB containers
- Alembic migrations (13 versions) document schema evolution — useful reference for Cosmos DB container schemas

### Integration Points
- Phase 18 (Auth) depends on Managed Identities and Key Vault provisioned here
- Phase 19 (Data) depends on Cosmos DB account and containers provisioned here
- Phase 20 (AKS) depends on AKS cluster and ACR provisioned here
- Phase 22 (CI/CD) depends on ACR for image push targets

</code_context>

<specifics>
## Specific Ideas

- User explicitly chose simplicity over enterprise lockdown — public access for all resources, single environment, single resource group
- Naming convention uses company prefix (`stumsft-aiplatform-*`) for organizational clarity
- Serverless Cosmos DB chosen to minimize cost for internal platform usage patterns

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 17-infrastructure-foundation-bicep-iac*
*Context gathered: 2026-03-26*
