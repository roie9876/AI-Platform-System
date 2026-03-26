# Phase 17: Infrastructure Foundation (Bicep IaC) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-26
**Phase:** 17-infrastructure-foundation-bicep-iac
**Areas discussed:** Module structure & naming, Networking topology, Cosmos DB container design, Environment parameterization

---

## Module Structure & Naming

### Directory Layout

| Option | Description | Selected |
|--------|-------------|----------|
| infra/ at repo root | infra/main.bicep, infra/modules/, infra/parameters/ — standard Azure convention | ✓ |
| deploy/bicep/ | deploy/ folder with bicep/ subfolder — groups all deployment artifacts | |
| You decide | Agent's discretion based on Azure best practices | |

**User's choice:** infra/ at repo root
**Notes:** Standard Azure convention, clean separation from app code.

### Module Organization

| Option | Description | Selected |
|--------|-------------|----------|
| Flat modules | infra/modules/aks.bicep, infra/modules/cosmos.bicep, etc. — one file per resource type | ✓ |
| Nested by category | infra/modules/compute/aks.bicep, infra/modules/network/vnet.bicep, etc. | |
| You decide | Agent's discretion | |

**User's choice:** Flat modules
**Notes:** Simple, each resource type is one file.

### Parameter Files

| Option | Description | Selected |
|--------|-------------|----------|
| .bicepparam files | Bicep-native parameter files with type safety | ✓ |
| JSON parameter files | Traditional ARM-style, broader tool support | |
| You decide | Agent's discretion | |

**User's choice:** .bicepparam files

### Azure Resource Naming

| Option | Description | Selected |
|--------|-------------|----------|
| Company-project-env-resource | stumsft-aiplatform-{env}-{resource} | ✓ |
| Project-env-resource | aiplatform-{env}-{resource} (shorter) | |
| You decide | Agent's discretion | |

**User's choice:** Company-project-env-resource (stumsft-aiplatform-{env}-{resource})

---

## Networking Topology

### VNet Design

| Option | Description | Selected |
|--------|-------------|----------|
| Single VNet, 3 subnets | aks-nodes, aks-pods (Azure CNI Overlay), private-endpoints | ✓ |
| Hub-spoke topology | Hub VNet for shared services, spoke VNet for AKS | |
| You decide | Agent's discretion | |

**User's choice:** Single VNet, 3 subnets

### Private Endpoints

| Option | Description | Selected |
|--------|-------------|----------|
| All private endpoints now | Private endpoints for Cosmos DB, ACR, Key Vault from day one | |
| Private endpoints for staging/prod only | Public access for dev, private for staging/prod | |
| All public (free text) | All resources public access for simplicity | ✓ |

**User's choice:** All public access for simplicity — no private endpoints.
**Notes:** User explicitly chose simplicity over enterprise lockdown.

---

## Cosmos DB Container Design

### Container Pre-creation

| Option | Description | Selected |
|--------|-------------|----------|
| All containers upfront | Pre-create all containers matching 13+ SQLAlchemy models | ✓ |
| Minimal containers now | Only database + 2-3 core containers; rest in Phase 19 | |
| You decide | Agent's discretion | |

**User's choice:** All containers upfront

### Throughput Mode

| Option | Description | Selected |
|--------|-------------|----------|
| Serverless | Pay-per-request, no minimum cost | ✓ |
| Autoscale provisioned | 400-4000 RU/s autoscale | |
| Shared database throughput | One RU pool shared across containers | |
| You decide | Agent's discretion | |

**User's choice:** Serverless

---

## Environment Parameterization

### Resource Group Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| RG per environment | rg-aiplatform-dev, rg-aiplatform-staging, rg-aiplatform-prod | |
| Single RG with tags | Single resource group with environment tags | ✓ |

**User's choice:** Single RG with tags

### AKS Node Sizing

| Option | Description | Selected |
|--------|-------------|----------|
| Progressive sizing | Dev: 1 node B2ms, Staging: 2 nodes D2s_v5, Prod: 3 nodes D4s_v5 | ✓ |
| Uniform SKU, varying count | Same SKU, different node counts | |
| You decide | Agent's discretion | |

**User's choice:** Progressive sizing (but single prod env only — 3 nodes Standard_D4s_v5)

### Environment Strategy (free text)

**User's choice:** Single production environment only — no dev/staging/test.
**Notes:** User explicitly stated "i dont want to have dev,test,prod for this project single prod env." One `.bicepparam` file only.

---

## Agent's Discretion

- NSG rule specifics, Key Vault access mode, ACR SKU, Log Analytics retention, Managed Identity naming

## Deferred Ideas

None — discussion stayed within phase scope
