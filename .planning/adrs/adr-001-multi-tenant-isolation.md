# ADR-001: Multi-Tenant Isolation Strategy

**Status:** Accepted
**Date:** 2026-03-23
**Affects:** All phases (1–11)

## Context

The AI Platform System is a multi-tenant SaaS platform where multiple organizations (tenants) and projects share the same infrastructure. Isolation decisions affect security, cost, operations, and compliance across every layer.

## Decision

**Shared infrastructure with logical isolation** — all tenants share the same physical resources. Isolation is enforced through Azure-native mechanisms at each layer.

## Per-Layer Isolation Strategy

### Network (Phase 1)
| Component | Strategy |
|-----------|----------|
| VNet | Single hub-spoke topology shared by all tenants |
| Subnets | Per-service-type (AKS, APIM, databases), not per-tenant |
| Private Endpoints | Shared — all PaaS access through the same private endpoints |
| NSGs | Per-subnet rules enforce service-to-service boundaries |
| Azure Firewall | Shared egress filtering — rules by service, not by tenant |
| Front Door | Single ingress point with WAF; tenant context in request headers |

**Rationale:** Per-tenant VNets don't scale. Subnet-per-service provides network-level blast radius containment without O(n) networking costs.

### Compute — AKS (Phases 1, 3+)
| Component | Strategy |
|-----------|----------|
| Cluster | Single AKS cluster per environment (dev/staging/prod) |
| Namespaces | Per-service (`catalog-service`, `deployment-service`), not per-tenant |
| Pod isolation | Tenant context in request headers; application-level routing |
| Resource limits | Per-service quotas in Kubernetes; per-tenant quotas enforced in application layer |
| Node pools | Shared system + user pools; GPU pool (Phase 5) also shared |

**Rationale:** Namespace-per-tenant creates O(n) operational burden (RBAC, network policies, deployments). Application-level multi-tenancy with shared services is the industry-standard SaaS pattern.

### API Gateway — APIM (Phase 6)
| Component | Strategy |
|-----------|----------|
| Gateway | Single APIM instance (Premium v2) shared by all tenants |
| Subscriptions | Per-project subscription keys for quota tracking |
| Rate limiting | Per-project rate limits via APIM policies |
| Routing | Project ID in request determines model routing and quota bucket |

**Rationale:** APIM natively supports per-subscription rate limiting. Each project gets its own subscription key, making quota enforcement automatic without custom code.

### Database — Cosmos DB (Phase 3)
| Component | Strategy |
|-----------|----------|
| Account | Single Cosmos DB account per environment |
| Containers | Shared containers with hierarchical partition keys |
| Partition key | `/tenantId/projectId/entityType` — ensures data locality and isolation |
| Cross-tenant queries | Impossible by design — queries scoped to partition key prefix |
| RU budgets | Per-partition key throttling via Cosmos DB native capabilities |

**Rationale:** Hierarchical partition keys (2024 GA) provide physical data isolation within shared containers. A query for `tenantA/project1` never reads `tenantB` data — the storage engine enforces this at the partition level. This is strictly stronger than row-level-security and avoids the DBA overhead of per-tenant databases.

### Database — Azure SQL (Phase 9)
| Component | Strategy |
|-----------|----------|
| Server | Single Azure SQL Hyperscale server per environment |
| Database | Shared database |
| Isolation | Row-level security (RLS) policies filter by `project_id` |
| Use case | Billing and cost aggregation (tabular data with complex joins) |

**Rationale:** Azure SQL RLS is a proven pattern for billing data. Billing queries need cross-project aggregation (admin views) which RLS handles cleanly with security policies.

### Identity — Entra ID (Phase 2)
| Component | Strategy |
|-----------|----------|
| Authentication | Single Entra ID app registration; all users authenticate to same app |
| Authorization | Application-level RBAC (Owner/Contributor/Reader) scoped per project |
| Token claims | Custom claims include `projectMemberships[]` with roles per project |
| Service-to-service | Managed identities — no per-tenant service principals |

**Rationale:** Entra ID handles authentication; the platform handles authorization. Project membership and role scoping is application logic — simpler and more flexible than Entra ID group-per-project.

### Secrets — Key Vault (Phase 1)
| Component | Strategy |
|-----------|----------|
| Vault | One Key Vault per environment; shared by all services |
| Access model | RBAC (not access policies); managed identity per service |
| Tenant secrets | Per-tenant API keys stored with naming convention: `{projectId}-api-key` |
| Rotation | Azure-native certificate/secret rotation |

**Rationale:** Key Vault RBAC + managed identities mean each service only reads its own secrets. No tenant can access another tenant's secrets because services mediate all access.

### Monitoring — Azure Monitor (Phases 1, 8)
| Component | Strategy |
|-----------|----------|
| Log Analytics | Single workspace per environment; all services log here |
| App Insights | Single instance connected to Log Analytics |
| Tenant isolation | `projectId` custom dimension on all telemetry |
| Dashboard access | KQL queries filtered by `projectId`; user-facing dashboards show only their projects |
| Admin views | Platform admins see cross-project metrics; project users see only their data |

**Rationale:** Single workspace simplifies operations. Custom dimensions enable per-project filtering without per-tenant workspaces. Dashboard RBAC is application-enforced.

### Storage & Artifacts (Phases 4–5)
| Component | Strategy |
|-----------|----------|
| ACR | Shared registry for platform service images (not per-tenant) |
| Blob Storage | Shared storage account; project-scoped containers or path prefixes (`/projects/{id}/`) |
| Model artifacts | Stored under project-scoped paths; SAS tokens scoped to path prefix |

**Rationale:** Project-scoped paths with SAS token isolation provide sufficient boundaries without per-tenant storage accounts.

### Cost & Billing (Phase 9)
| Component | Strategy |
|-----------|----------|
| Cost attribution | Token usage tagged with `projectId` at inference time |
| Budget enforcement | Application-level budget checks per project |
| Billing export | Per-project cost rollups with model/deployment/time breakdowns |

**Rationale:** Cost attribution is a software concern. Azure resource tags track infrastructure cost; application-level token counting tracks per-project consumption cost.

## Alternatives Considered

### 1. Namespace-per-Tenant (Rejected)
Each tenant gets a Kubernetes namespace with dedicated services. Rejected because:
- O(n) deployment complexity — every new tenant requires new deployments
- Resource waste — idle tenants still consume pod reservations
- Operational burden — namespace RBAC, network policies, resource quotas per tenant

### 2. Database-per-Tenant (Rejected)
Each tenant gets its own Cosmos DB database/container. Rejected because:
- Cosmos DB charges per-container minimum RUs — 100 tenants = 100x base cost
- Schema migrations must run N times
- Connection management doesn't scale

### 3. VNet-per-Tenant (Rejected)
Complete network isolation per tenant. Rejected because:
- Azure VNet peering limits and costs
- Private endpoint duplication
- Disproportionate cost for the security benefit

## Consequences

- **Positive:** Cost-efficient at scale, single operational surface, Azure-native isolation
- **Negative:** Bugs in application-level isolation could leak data cross-tenant (mitigated by partition keys and RBAC at multiple layers)
- **Risk:** A noisy-neighbor tenant could impact shared resources (mitigated by per-project rate limiting at APIM and per-partition throttling in Cosmos DB)

## References

- Azure Well-Architected Framework: Multi-tenancy
- Cosmos DB hierarchical partition keys documentation
- APIM subscription-based rate limiting
- AKS multi-tenant best practices
