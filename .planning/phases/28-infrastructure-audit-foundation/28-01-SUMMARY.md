# Plan 28-01 Summary: Cosmos DB + Bicep Infrastructure Modules

## Status: Complete

## Changes Made

### Task 1: Cosmos DB DiskANN + Token Logs
- **Modified** `infra/modules/cosmos.bicep`:
  - Removed `agent_memories` from bulk `containerNames` array
  - Added standalone `tokenLogsContainer` resource with 90-day TTL (`defaultTtl: 7776000`), partitioned by `/tenant_id`
  - Added standalone `agentMemoriesContainer` resource with DiskANN vector embedding policy (1536 dimensions, float32, cosine distance function) and vector index on `/embedding`

### Task 2: DNS, Domain, Tenant Key Vault Modules + Main Wiring
- **Created** `infra/modules/dns.bicep`: Azure DNS zone resource for custom agent subdomains
- **Created** `infra/modules/domain.bicep`: App Service Domains for buy-via-Azure option with ICANN contact params
- **Created** `infra/modules/keyvault-tenants.bicep`: Tenant Key Vault (`stumsft-aiplat-${env}-tkv`) with RBAC (Key Vault Secrets User role), diagnostics, soft delete
- **Modified** `infra/main.bicep`:
  - Added 7 new parameters (agentsDomain, buyDomain, domainContact*)
  - Added conditional DNS zone module (`if (!empty(agentsDomain))`)
  - Added conditional domain purchase module (`if (buyDomain && !empty(agentsDomain))`)
  - Added tenant Key Vault module in Wave 4
  - Added 4 new outputs (tenantKeyVaultName, tenantKeyVaultUri, dnsNameServers, agentsDomain)
- **Modified** `infra/parameters/prod.bicepparam`: Added all new params with safe defaults (empty/false)

## Verification
- `az bicep build --file infra/main.bicep` — clean compilation
- All grep checks passed for token_logs, vectorEmbeddingPolicy, diskANN markers
- All new module files exist and contain expected resource types

## Requirements Covered
- AUDIT-01 (partial): Infrastructure gaps filled in Bicep
- AUDIT-05 (partial): Tenant Key Vault provisioned via Bicep
