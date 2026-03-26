# Technology Stack — v3.0 Production Multi-Tenant Infrastructure Additions

**Project:** AI Agent Platform as a Service
**Researched:** 2026-03-26
**Scope:** NEW stack additions only — existing Python/FastAPI, Next.js, SQLAlchemy/PostgreSQL, Docker Compose stack is validated and NOT repeated here.

---

## Recommended Stack Additions

### 1. Azure IaC — Bicep Tooling

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Azure CLI | ≥2.84.0 | ARM deployment, AKS management, ACR operations | Required for `az deployment`, `az aks`, `az acr` commands. Bicep is bundled. |
| Bicep CLI | ≥0.40.2 (bundled with Azure CLI) | Infrastructure-as-Code authoring | Microsoft-native IaC. Type-safe, no state file (vs Terraform), first-class Azure support. ARM template compilation built-in. |
| Bicep VS Code Extension | latest | Authoring support | Validation, IntelliSense, linting for `.bicep` files. |

**Why Bicep over Terraform:** Decided in PROJECT.md — Microsoft-native, first-class Azure support, type-safe, no remote state management. For an Azure-only deployment targeting 2-5 tenants, Bicep is simpler and more tightly integrated.

**What NOT to add:** Terraform, Pulumi, or CDK for Terraform. Bicep is the decided IaC tool.

**Integration with existing stack:** Bicep modules live in `infra/` directory at repo root. No backend code changes needed — Bicep operates at the infrastructure layer.

---

### 2. Cosmos DB Data Layer

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| azure-cosmos | **4.15.0** | Cosmos DB NoSQL data operations | Latest stable. Async support via `azure.cosmos.aio`. Native partition key support for tenant isolation. |
| azure-mgmt-cosmosdb | **9.9.0** | Cosmos DB account/database provisioning (optional, Bicep handles most) | Management plane ops if dynamic container creation needed at runtime. |

**Async Support (CRITICAL):** The `azure-cosmos` SDK supports async natively since 4.3.0:
```python
from azure.cosmos.aio import CosmosClient

async with CosmosClient(url, credential) as client:
    database = client.get_database_client("aiplatform")
    container = database.get_container_client("agents")
    items = container.query_items(
        query="SELECT * FROM c WHERE c.tenant_id=@tid",
        parameters=[{"name": "@tid", "value": tenant_id}],
        partition_key=tenant_id
    )
    async for item in items:
        ...
```

**Python ORM Changes — SQLAlchemy Replacement Strategy:**

SQLAlchemy does NOT support Cosmos DB. The migration requires:

1. **Drop SQLAlchemy ORM layer** for Cosmos DB-backed entities (agents, threads, tools, workflows, etc.)
2. **Introduce a Repository Pattern** — abstract data access behind `Repository` interfaces so services don't depend on the storage backend directly
3. **Keep SQLAlchemy for local dev** if a PostgreSQL fallback is desired during development (optional)
4. **Pydantic models become the canonical schema** — Cosmos DB stores JSON documents; Pydantic `BaseModel` classes define document shape and validation

| What Changes | From | To |
|--------------|------|-----|
| ORM layer | SQLAlchemy async ORM + Alembic migrations | `azure-cosmos` async SDK + Repository pattern |
| Schema definition | SQLAlchemy `Base` models in `app/models/` | Pydantic document models (schema-on-write) |
| Migrations | Alembic version scripts | No schema migrations — Cosmos DB is schemaless. Container provisioning in Bicep. |
| Query builder | SQLAlchemy `select()` / `filter()` | Cosmos DB SQL API queries (parameterized) |
| Connection management | `async_sessionmaker` / `get_db()` | `CosmosClient` singleton with async context manager |
| Partition strategy | None (single PostgreSQL DB) | `tenant_id` as partition key on every container |

**What NOT to add:**
- No ORMs for Cosmos DB (they don't exist in a meaningful way)
- No `odmantic` or `beanie` (those are MongoDB-specific)
- No `opencensus` extensions (deprecated)

---

### 3. AKS Deployment Tooling

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| kubectl | **v1.30.x** | Kubernetes cluster operations | Direct cluster management, namespace creation, RBAC setup. Already installed. |
| Helm | **v4.0.x** | Kubernetes package management | Chart-based deployment for the microservice suite. One chart per service with shared values. Better than raw manifests for multi-service apps. |
| Kustomize | **v5.0.x** (built into kubectl) | Environment-specific overlays | Per-environment (dev/staging/prod) and per-tenant namespace overlays. Complements Helm for tenant-specific configs. |

**Why Helm + Kustomize (not one or the other):**
- **Helm** for packaging each microservice as a chart with templates, versioned releases, rollback support
- **Kustomize** for tenant-specific namespace overlays (`kustomize build overlays/tenant-a/`) — simpler than Helm values for namespace-per-tenant isolation
- Use Helm for the services, Kustomize for tenant provisioning overlays

**What NOT to add:**
- Skaffold (dev tooling, not needed for CI/CD — Docker Compose handles local dev)
- Tilt (same — local dev is Docker Compose)
- ArgoCD or Flux (GitOps is overkill for 2-5 tenants, GitHub Actions is sufficient)

**AKS Management SDK (optional):**

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| azure-mgmt-containerservice | **41.0.0** | Programmatic AKS cluster operations | Only if the tenant provisioning API needs to interact with AKS control plane (e.g., node pool scaling). Bicep handles initial provisioning. |

---

### 4. Microsoft Entra ID Authentication

#### Backend SDKs

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| azure-identity | **1.25.3** | Managed Identity credential, token acquisition for service-to-service auth | Unified credential chain: `DefaultAzureCredential` works in local dev (Azure CLI), AKS (Workload Identity), and VMs (Managed Identity). |
| msal | **1.35.1** | JWT token validation for Entra ID access tokens on the backend | Validates Entra ID tokens from the frontend. Provides token cache and authority discovery. |
| PyJWT | 2.10.1 (existing) | JWT decode/verify | Already in stack. Will be used alongside `msal` for token verification. Keep for backward compatibility during migration. |
| cryptography | 44.0.0 (existing) | JWKS key handling | Already in stack. Required for RS256 token validation with Entra ID public keys. |

**Backend Auth Migration:**

| What Changes | From | To |
|--------------|------|-----|
| Token signing | HS256 with `SECRET_KEY` (symmetric) | RS256 with Entra ID JWKS endpoint (asymmetric) |
| Token issuance | Backend issues tokens via `create_access_token()` | Entra ID issues tokens; backend validates them |
| Identity provider | Custom user table + bcrypt passwords | Microsoft Entra ID (Azure AD) |
| Service-to-service auth | None (monolith) | `DefaultAzureCredential` → Managed Identity tokens |
| Multi-tenant resolution | `X-Tenant-ID` header middleware | Entra ID `tid` claim in JWT + tenant lookup |

**What NOT to add:**
- `python-jose` (deprecated, PyJWT is sufficient)
- `authlib` (unnecessary — msal + PyJWT handles everything)
- Custom OAuth2 server implementations

#### Frontend SDKs (ALREADY IN STACK)

| Technology | Version | Status | Notes |
|------------|---------|--------|-------|
| @azure/msal-browser | ^5.6.1 | **Already installed** | Latest. No changes needed. |
| @azure/msal-react | ^5.1.0 | **Already installed** | Latest. No changes needed. |

**Frontend Auth Changes:**
- Add `MsalProvider` wrapping the app (using existing packages)
- Configure `PublicClientApplication` with tenant app registration
- Add `loginRedirect` / `acquireTokenSilent` flows
- No new npm packages needed

---

### 5. GitHub Actions CI/CD

| Action | Version | Purpose | Why |
|--------|---------|---------|-----|
| azure/login | **@v2** | Authenticate to Azure via OIDC (federated credentials) | Required first step for all Azure operations. OIDC eliminates stored secrets. |
| docker/login-action | **@v3** | ACR container registry login | **Use this, NOT `Azure/docker-login`** which is deprecated/unmaintained. Works with ACR via `azure/login` token. |
| docker/build-push-action | **@v6** | Build and push container images to ACR | Multi-platform builds, layer caching, buildx support. |
| azure/setup-kubectl | **@v4** | Install kubectl in the runner | Required for k8s operations. |
| azure/aks-set-context | **@v5** | Set AKS cluster kubeconfig | Just released. OIDC + kubelogin support. |
| Azure/k8s-deploy | **@v5** | Deploy Kubernetes manifests | Manifest substitution, rollout status checks, canary/blue-green support. |
| Azure/k8s-create-secret | **@v5** | Create K8s secrets for image pull | Docker registry secrets for ACR in each tenant namespace. |
| azure/use-kubelogin | **@v1.2** | Non-interactive AKS auth via kubelogin | Required for non-admin service principal deployments on AKS. |
| actions/checkout | **@v4** | Checkout source code | Standard. |

**Example Pipeline Structure:**
```yaml
# .github/workflows/deploy.yml
jobs:
  build:
    # Build each microservice image → push to ACR
    steps:
      - azure/login@v2 (OIDC)
      - docker/login-action@v3 (ACR)
      - docker/build-push-action@v6 (per service)

  deploy:
    # Deploy to AKS
    steps:
      - azure/login@v2 (OIDC)
      - azure/aks-set-context@v5
      - Azure/k8s-deploy@v5 (per namespace)
```

**What NOT to add:**
- `Azure/docker-login` (deprecated — maintainer recommends `docker/login-action`)
- `azure/webapps-deploy` (we're deploying to AKS, not App Service)
- Third-party Helm actions (kubectl + Helm CLI in runner is sufficient)

---

### 6. Azure Observability

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| azure-monitor-opentelemetry | **1.8.7** | Azure Monitor OpenTelemetry distro (all-in-one) | Official Microsoft package. Auto-instruments FastAPI, httpx, requests, logging. Exports to App Insights. **Replaces deprecated opencensus-ext-azure.** |
| opentelemetry-api | **1.40.0** | OpenTelemetry API for custom spans/metrics | Core OTel API. Used for custom instrumentation (per-tenant spans, agent execution traces). |
| opentelemetry-sdk | **1.40.0** | OpenTelemetry SDK implementation | Core OTel SDK. Configured via `azure-monitor-opentelemetry` distro. |

**Why `azure-monitor-opentelemetry` (NOT individual packages):**
The distro bundles and configures all needed instrumentations:
- `opentelemetry-instrumentation-fastapi` (HTTP traces)
- `opentelemetry-instrumentation-httpx` (outbound HTTP calls)
- `opentelemetry-instrumentation-redis` (cache operations)
- `opentelemetry-instrumentation-logging` (log correlation)
- Azure Monitor exporter (sends to App Insights)

One import, one configure call:
```python
from azure.monitor.opentelemetry import configure_azure_monitor

configure_azure_monitor(
    connection_string="InstrumentationKey=...",
    resource={"service.name": "api-gateway", "tenant.id": tenant_id}
)
```

**What NOT to add:**
- `opencensus-ext-azure` (DEPRECATED — replaced by `azure-monitor-opentelemetry`)
- `applicationinsights` Python SDK (legacy, use OTel distro)
- Individual `opentelemetry-instrumentation-*` packages (the distro bundles them)
- Prometheus/Grafana stack (Azure Monitor is the decided observability platform)

---

### 7. Container Tooling — Multi-Stage Dockerfile Pattern

**No new packages** — this is a Dockerfile architecture change.

**Current state:** Single-stage Dockerfile (6 lines, copies everything, no build optimization).

**Required pattern for production microservices:**

```dockerfile
# Stage 1: Dependencies
FROM python:3.12-slim AS deps
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Production
FROM python:3.12-slim AS production
WORKDIR /app

# Non-root user for security
RUN addgroup --system app && adduser --system --ingroup app app

# Copy only installed packages + source
COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin
COPY . .

USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Frontend multi-stage (Next.js standalone):**
```dockerfile
# Stage 1: Dependencies + Build
FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: Production
FROM node:22-alpine AS production
WORKDIR /app
RUN addgroup --system app && adduser --system --ingroup app app

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

USER app
EXPOSE 3000
CMD ["node", "server.js"]
```

**Key changes:**
- Multi-stage builds (smaller images, no build tools in prod)
- Non-root user (`USER app`)
- Separate Dockerfile per microservice
- `.dockerignore` files to exclude `.venv`, `node_modules`, `__pycache__`, `.git`

---

### 8. Supporting Infrastructure Libraries

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| azure-keyvault-secrets | **4.10.0** | Secret retrieval from Key Vault | Store Cosmos DB keys, connection strings, app secrets in Key Vault instead of env vars. Managed Identity auth via `DefaultAzureCredential`. |
| azure-identity | 1.25.3 | (listed above) | `DefaultAzureCredential` for all Azure SDK auth — one credential, works everywhere. |

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| IaC | Bicep | Terraform | Project decision — Bicep is Azure-native, no state management |
| K8s packaging | Helm + Kustomize | Raw manifests | Too verbose for 5+ microservices × N tenants |
| K8s packaging | Helm + Kustomize | Helm only | Kustomize better for tenant namespace overlays |
| Observability | azure-monitor-opentelemetry | opencensus-ext-azure | opencensus is deprecated; OTel is the standard |
| Observability | azure-monitor-opentelemetry | Prometheus + Grafana | Project decision — Azure Monitor is the platform |
| Container login | docker/login-action | Azure/docker-login | Azure/docker-login is deprecated/unmaintained |
| Data access | Repository pattern + azure-cosmos SDK | SQLAlchemy + custom Cosmos dialect | No SQLAlchemy Cosmos dialect exists; SDK is the way |
| GitOps | GitHub Actions | ArgoCD / Flux | Overkill for 2-5 tenants; GitHub Actions is sufficient |
| Auth tokens | Entra ID + msal | Custom OAuth2 server | Enterprise SSO requirement; don't build what Entra provides |

---

## Installation — New Backend Dependencies

```bash
# Core Azure SDKs (add to requirements.txt)
azure-cosmos==4.15.0
azure-identity==1.25.3
azure-keyvault-secrets==4.10.0
msal==1.35.1

# Observability
azure-monitor-opentelemetry==1.8.7

# Management SDKs (optional — only if runtime provisioning needed)
azure-mgmt-containerservice==41.0.0
azure-mgmt-cosmosdb==9.9.0
```

## Installation — New Frontend Dependencies

```bash
# NONE — @azure/msal-browser and @azure/msal-react already installed
```

## Installation — CLI Tools (Developer Workstation / CI Runner)

```bash
# Azure CLI (includes Bicep)
brew install azure-cli
az bicep install  # or upgrade: az bicep upgrade

# Kubernetes tools
brew install kubectl helm kustomize

# Already installed versions confirmed:
# az: 2.84.0, bicep: 0.40.2, kubectl: 1.30.5, helm: 4.0.1
```

---

## Integration Points with Existing Stack

| Existing Component | Integration Impact | What Changes |
|--------------------|-------------------|--------------|
| FastAPI backend (`app/main.py`) | Add OTel middleware, Entra ID auth dependency | New middleware, auth module refactored |
| SQLAlchemy models (`app/models/`) | Replaced for Cosmos-backed entities | New Pydantic document models + Repository classes |
| Alembic migrations | No longer needed for Cosmos entities | Alembic stays only if PostgreSQL kept for any data |
| `database.py` (`get_db()`) | Replace with Cosmos client factory | New `get_cosmos_db()` dependency |
| `security.py` | Token validation changes from HS256→RS256 | Validate Entra ID tokens instead of self-issued |
| `tenant.py` middleware | Enhanced with Entra ID `tid` claim | Read tenant from JWT claims, not just header |
| `config.py` Settings | New Azure config fields | Add `COSMOS_URL`, `COSMOS_KEY`, `APPINSIGHTS_CONNECTION_STRING`, `AZURE_TENANT_ID`, `AZURE_CLIENT_ID` |
| Docker Compose | Kept for local dev | Add Cosmos DB emulator container, keep PostgreSQL |
| Dockerfile | Multi-stage refactor | Per-service Dockerfiles in service directories |
| Frontend MSAL packages | Already installed | Add `MsalProvider` configuration, auth context |
| `requirements.txt` | Add new Azure packages | 5-7 new dependencies |
| Redis | No change | Continue using for caching, rate limiting |

---

## What NOT to Add (Explicit Exclusions)

| Technology | Why Not |
|------------|---------|
| Terraform / Pulumi | Decided: Bicep is the IaC tool |
| MongoDB drivers / Beanie / ODMantic | Cosmos DB uses its own SDK, not MongoDB-compatible drivers |
| SQLAlchemy Cosmos dialect | Doesn't exist — use native SDK |
| opencensus-ext-azure | Deprecated — replaced by azure-monitor-opentelemetry |
| applicationinsights SDK | Legacy — OTel distro is the replacement |
| ArgoCD / Flux | Overkill — GitHub Actions handles CI/CD for 2-5 tenants |
| Istio / Linkerd service mesh | Overkill — Kubernetes NetworkPolicy sufficient for tenant isolation |
| python-jose | Deprecated — PyJWT (already in stack) is sufficient |
| Prometheus + Grafana | Azure Monitor is the decided platform |
| Azure/docker-login action | Deprecated — use docker/login-action |

---

## Sources

| Claim | Source | Confidence |
|-------|--------|------------|
| azure-cosmos 4.15.0 latest, async since 4.3.0 | pip index (2026-03-26) | HIGH |
| azure-identity 1.25.3 latest | pip index (2026-03-26) | HIGH |
| azure-monitor-opentelemetry 1.8.7 latest | pip index (2026-03-26) | HIGH |
| msal 1.35.1 latest | pip index (2026-03-26) | HIGH |
| opentelemetry-api/sdk 1.40.0 latest | pip index (2026-03-26) | HIGH |
| azure-mgmt-containerservice 41.0.0 latest | pip index (2026-03-26) | HIGH |
| Azure CLI 2.84.0, Bicep 0.40.2 | `az version` local (2026-03-26) | HIGH |
| kubectl 1.30.5, Helm 4.0.1 | Local toolchain (2026-03-26) | HIGH |
| Azure/docker-login deprecated | GitHub README warning banner (2026-03-26) | HIGH |
| Azure/aks-set-context@v5 | GitHub releases (2026-03-26) | HIGH |
| Azure/k8s-deploy@v5.1.0 | GitHub releases (2026-03-26) | HIGH |
| docker/login-action@v3 | GitHub marketplace (2026-03-26) | HIGH |
| @azure/msal-browser 5.6.1, @azure/msal-react 5.1.0 | npm registry + existing package.json | HIGH |
| SQLAlchemy has no Cosmos DB dialect | Training data + no pip package exists | HIGH |
| opencensus-ext-azure deprecated | Azure SDK deprecation notices, replaced by OTel distro | HIGH |
