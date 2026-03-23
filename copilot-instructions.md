<!-- GSD:project-start source:PROJECT.md -->
## Project

**AI Platform System**

A comprehensive AI platform system — similar to Azure AI Foundry, Google Vertex AI, and AWS Bedrock — that provides a unified interface for discovering, deploying, managing, and consuming AI models and services. Built on Azure Cloud, it serves as an enterprise-grade AI orchestration platform enabling developers and organizations to build, train, fine-tune, deploy, and monitor AI/ML models at scale.

**Core Value:** Provide a single, unified platform where users can discover AI models from multiple providers, deploy them with one click, and consume them through standardized APIs — eliminating the complexity of managing disparate AI services.

### Constraints

- **Cloud:** Azure-only deployment — leverage Azure-native services (AKS, Cosmos DB, API Management, Azure OpenAI, etc.)
- **Security:** Enterprise-grade — SOC 2, Azure compliance, data encryption at rest and in transit
- **Architecture:** Microservices on AKS with event-driven patterns
- **Auth:** Azure Entra ID (formerly Azure AD) for identity and RBAC
- **IaC:** Bicep/ARM templates for all infrastructure provisioning
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Recommended Stack
### Core Application Framework
| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| TypeScript | 5.7+ | Primary language (full-stack) | Type safety across backend/frontend reduces bugs at scale. Single language for entire platform eliminates context switching. Azure SDKs have first-class TypeScript support. |
| NestJS | 11.x (11.1.17) | Backend microservices framework | Architecture-opinionated (DI, modules, guards, interceptors) — essential for enterprise platform with 10+ microservices. Built-in microservices transport (gRPC, MQTT, Redis, NATS). Angular-inspired patterns provide consistency across large teams. 3.7M+ weekly npm downloads. |
| Next.js | 16.x (16.2) | Frontend web application | React 19.2 with Server Components, Turbopack stable, cache components for instant navigation. App Router with PPR (Partial Pre-Rendering) is ideal for the dashboard-heavy admin console. Self-hostable on AKS (not locked to Vercel). |
| React | 19.2 | UI library | Ships with Next.js 16. View Transitions, `useEffectEvent()`, `<Activity/>` for complex interactive UIs like prompt playground and model catalog. |
| Node.js | 22 LTS | Runtime | LTS until April 2027. Native fetch, ESM stable, performance improvements. Required by NestJS 11. |
### Azure Cloud Services — Compute
| Technology | Tier/SKU | Purpose | Why Recommended |
|------------|----------|---------|-----------------|
| Azure Kubernetes Service (AKS) | Standard | Container orchestration for all microservices | Specified in project constraints. CNCF-certified, SOC/ISO/PCI compliant. Native integration with Entra ID, Azure Monitor, KEDA autoscaling. Supports GPU node pools for model inference workloads. |
| Azure Container Registry (ACR) | Premium | Docker image storage | Geo-replication for multi-region deployment, content trust for image signing, Microsoft Defender integration for vulnerability scanning. Connects directly to AKS via managed identity. |
| Azure Functions | Flex Consumption | Event-driven compute (webhooks, async processing) | Recommended plan per Microsoft (replaces legacy Consumption). Fast scaling, VNet integration, pay-per-use. Use for lightweight event handlers: model deployment callbacks, notification dispatch, scheduled cleanup jobs. |
### Azure Cloud Services — Data
| Technology | Tier/SKU | Purpose | Why Recommended |
|------------|----------|---------|-----------------|
| Azure Cosmos DB | NoSQL API (Serverless/Autoscale) | Primary operational database | Multi-model (document + vector), hierarchical partition keys for multi-tenant isolation, change feed for event-driven patterns, integrated vector search (DiskANN) for model catalog semantic search. 99.999% SLA with multi-region writes. SDKs for .NET, Java, JavaScript, Python. Azure's recommended AI database. |
| Azure Cache for Redis | Premium (P1+) | Caching, session store, rate limiting | Sub-millisecond latency for API response caching, model metadata caching, rate limit counters. VNet support, data persistence, active geo-replication. |
| Azure Blob Storage | Hot/Cool tiers | Datasets, model artifacts, evaluation results | Unlimited storage, lifecycle policies for cost optimization. Hierarchical namespace (Data Lake Gen2) for training data organization. Direct integration with Azure ML and Spark. |
| Azure SQL Database | Hyperscale/Serverless | Billing, audit logs, relational data | Relational data (billing records, quota tracking, audit trails) doesn't fit Cosmos DB's NoSQL model. Hyperscale scales to 100TB. Auto-pause saves cost on dev/test environments. |
### Azure Cloud Services — Messaging & Events
| Technology | Tier/SKU | Purpose | Why Recommended |
|------------|----------|---------|-----------------|
| Azure Service Bus | Premium | Inter-service messaging (commands, events) | Enterprise message broker with transactions, sessions, dead-lettering, duplicate detection. FIFO guarantees for deployment orchestration. Premium tier for VNet integration and 1MB+ messages. Use for: deployment pipelines, fine-tuning job orchestration, cross-service commands. |
| Azure Event Hubs | Standard/Premium | High-throughput telemetry & usage streaming | Millions of events/second for API usage telemetry, model inference metrics, cost tracking data. Apache Kafka protocol compatible. Capture feature writes to Blob Storage for batch analytics. Schema Registry for governed data contracts. Use for: usage metering, inference logging, audit events. |
### Azure Cloud Services — Networking & API
| Technology | Tier/SKU | Purpose | Why Recommended |
|------------|----------|---------|-----------------|
| Azure API Management (APIM) | Premium v2 | API gateway for model consumption APIs | Built-in AI gateway capabilities for Azure OpenAI (load balancing, token rate limiting, semantic caching). VNet injection for full network isolation. Workspaces for federated API management per team. Developer portal for API documentation. Handles JWT validation, API key management, usage quotas — core platform requirements. |
| Azure Front Door | Premium | Global load balancing, WAF, CDN | Global anycast for low-latency API access. Web Application Firewall (WAF) for DDoS protection. CDN for static frontend assets. TLS termination with custom domains. |
### Azure Cloud Services — AI & ML
| Technology | Version/SKU | Purpose | Why Recommended |
|------------|-------------|---------|-----------------|
| Azure OpenAI Service | GPT-5.x series, GPT-4.1, o-series, embeddings | Foundation model access | Direct access to GPT-5.4 (latest), GPT-5-mini/nano for cost-efficient inference, text-embedding-3-large for vector search. Global Standard deployment for high throughput. Fine-tuning support for GPT-4.1, GPT-5. Managed endpoints with auto-scaling. |
| Azure AI Content Safety | GA | Responsible AI guardrails | Prompt Shields for jailbreak detection, groundedness detection for hallucination prevention, protected material detection. Task adherence for AI agent safety. Multi-severity classification (text + image). Direct integration with APIM policies. |
| Azure AI Search | Standard S2+ | Advanced search over model catalog | Hybrid search (keyword + vector + semantic ranking). Integrated vectorization from Azure OpenAI embeddings. Faceted navigation for model catalog filtering. Skills pipeline for metadata enrichment. |
### Azure Cloud Services — Identity & Security
| Technology | Tier/SKU | Purpose | Why Recommended |
|------------|----------|---------|-----------------|
| Microsoft Entra ID | P2 | Identity provider, RBAC | Specified in constraints. Conditional access, PIM (Privileged Identity Management), identity governance. SCIM provisioning for enterprise customer onboarding. Managed identities for inter-service authentication (no secrets). |
| Azure Key Vault | Premium | Secrets, keys, certificates | HSM-backed keys (FIPS 140-3 Level 3). Store API keys, connection strings, encryption keys. Managed identity access — services never handle secrets directly. Certificate management for TLS. |
### Azure Cloud Services — Observability
| Technology | Purpose | Why Recommended |
|------------|---------|-----------------|
| Azure Monitor | Platform-wide metrics and alerts | Unified metrics for all Azure resources. Custom metrics for business KPIs (deployments/day, inference latency). Alert rules for SLA breaches. |
| Application Insights | APM, distributed tracing, live metrics | Auto-instrumentation for Node.js. End-to-end transaction tracing across microservices. Dependency maps, failure analysis, performance bottleneck detection. Smart detection for anomalies. |
| Log Analytics | Centralized logging, KQL queries | Workspace for all logs (application, infrastructure, security). KQL for complex queries. Workbooks for interactive dashboards. 90-day interactive retention, 2-year archive. |
### Azure Cloud Services — Infrastructure as Code
| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Bicep | Latest (GA) | IaC for all Azure resources | Specified in constraints. Declarative syntax, immediate support for new Azure API versions, VS Code extension with IntelliSense. Modules for reusable infrastructure components. What-if preview before deployment. No state files to manage (Azure stores state). |
### Supporting Libraries
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| @azure/identity | 4.x | Azure authentication (managed identity, tokens) | Every service connecting to Azure resources. DefaultAzureCredential for local dev + production. |
| @azure/cosmos | 4.x | Cosmos DB SDK | All database operations. Built-in retry, partial batch, hierarchical partition key support. |
| @azure/openai | 3.x | Azure OpenAI SDK | Model inference calls, embeddings, fine-tuning API. Streaming support for chat completions. |
| @azure/service-bus | 7.x | Service Bus SDK | Publishing commands/events between microservices. Session-based message processing. |
| @azure/event-hubs | 5.x | Event Hubs SDK | Telemetry ingestion, usage metering, audit event publishing. |
| @azure/storage-blob | 12.x | Blob Storage SDK | Dataset upload/download, model artifact management, evaluation result storage. |
| @azure/keyvault-secrets | 4.x | Key Vault SDK | Secret retrieval at service startup (for non-managed-identity scenarios). |
| @nestjs/microservices | 11.x | NestJS microservices transport | gRPC between internal services. Message pattern-based routing. |
| @grpc/grpc-js | 1.x | gRPC client/server | High-performance inter-service communication for model inference proxying. |
| bullmq | 5.x | Job queue (Redis-backed) | Long-running job management: fine-tuning orchestration, batch evaluation, data processing pipelines. |
| zod | 3.x | Schema validation | API request/response validation, configuration validation. TypeScript-first, composable schemas. |
| Prisma | 6.x | SQL ORM (Azure SQL) | Type-safe database access for billing, audit, and relational data. Migrations, introspection. |
| Helmet | 8.x | HTTP security headers | Express/Fastify security middleware. CSP, HSTS, X-Frame-Options. |
| pino | 9.x | Structured logging | High-performance JSON logging. Direct integration with Application Insights via pino-applicationinsights transport. |
| ioredis | 5.x | Redis client | Connection to Azure Cache for Redis. Cluster mode, Sentinel support. Used by BullMQ. |
| Commander.js | 12.x | CLI framework | Platform CLI tool for developers (`aip deploy`, `aip models list`). |
### Frontend Libraries
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Tailwind CSS | 4.x | Utility-first CSS | All component styling. JIT compilation, design system tokens. |
| shadcn/ui | Latest | Component library (Radix + Tailwind) | Pre-built accessible components. Copy-paste model — no dependency lock-in. Customizable via Tailwind. |
| TanStack Query | 5.x | Server state management | API data fetching, caching, pagination for model catalog, deployment lists, usage dashboards. |
| Recharts | 2.x | Data visualization | Usage charts, cost dashboards, model performance metrics, latency graphs. |
| Monaco Editor | 0.52+ | Code editor | Prompt playground, API request builder, configuration editing. Same editor as VS Code. |
| Zustand | 5.x | Client state management | Lightweight global state for UI (theme, sidebar, user preferences). Not for server state (use TanStack Query). |
### Development Tools
| Tool | Purpose | Notes |
|------|---------|-------|
| pnpm | Package manager | Faster installs, strict dependency resolution, workspace support for monorepo. |
| Turborepo | Monorepo build system | Parallel builds, remote caching, task dependencies. Works natively with pnpm workspaces. |
| Vitest | Unit/integration testing | Vite-powered, Jest-compatible API, native TypeScript/ESM. Fast watch mode. |
| Playwright | E2E testing | Cross-browser testing, API testing, component testing. Azure DevOps integration. |
| ESLint | Linting | v9 with flat config. @typescript-eslint for TypeScript rules. |
| Prettier | Code formatting | Consistent formatting across all packages. |
| Docker | Containerization | Multi-stage builds for minimal production images. Docker Compose for local dev. |
| Helm | Kubernetes package manager | Chart templating for AKS deployments. Values overrides per environment. |
| GitHub Actions | CI/CD pipelines | Build → Test → Push ACR → Deploy AKS. OIDC federation with Azure (no stored secrets). |
## Monorepo Structure
## Installation
# Initialize monorepo
# Core backend (per service)
# Frontend
# CLI
# Dev dependencies
## Alternatives Considered
| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Backend Framework | NestJS 11 (TypeScript) | ASP.NET Core 9 (.NET) | .NET is excellent for Azure, but PROJECT.md doesn't constrain language choice. TypeScript unifies frontend and backend, reducing cognitive overhead. NestJS microservices transport is more flexible than .NET's Dapr dependency. |
| Backend Framework | NestJS 11 (TypeScript) | FastAPI (Python) | Python is great for ML-focused platforms, but this platform _consumes_ models (not trains them). Python concurrency model (GIL) is inferior for high-throughput API proxy workloads. |
| Backend Framework | NestJS 11 (TypeScript) | Go (stdlib/gin) | Go has superior raw performance, but the team building an AI _platform_ (not infrastructure) benefits more from NestJS's architecture patterns, DI, decorators, and ecosystem. Higher development velocity. |
| Frontend Framework | Next.js 16 | Angular 19 | Angular is a valid choice (NestJS is Angular-inspired), but React/Next.js has broader ecosystem, faster iteration, and better community tooling for dashboards. Next.js SSR is superior to Angular SSR. |
| Frontend Framework | Next.js 16 | Vue/Nuxt 4 | Vue is excellent but smaller ecosystem for enterprise tooling. React has more battle-tested component libraries for complex admin UIs. |
| Database | Cosmos DB NoSQL | PostgreSQL (Azure Database for PostgreSQL) | PostgreSQL with pgvector could work, but Cosmos DB provides turnkey global distribution, multi-tenant partitioning, integrated vector search, and 99.999% SLA without operational overhead. Better fit for a multi-tenant SaaS platform. |
| Database | Cosmos DB + Azure SQL | Cosmos DB only | Billing/quota data is inherently relational (joins, transactions, aggregations). Cosmos DB's cost model (RU/s) is expensive for complex analytical queries. Azure SQL Hyperscale handles reporting workloads efficiently. |
| Message Broker | Service Bus + Event Hubs | RabbitMQ on AKS | Self-hosted RabbitMQ adds operational burden. Service Bus is Azure-native with managed identity, VNet, and SLA. Same features (queues, topics, dead-letter) without cluster management. |
| API Gateway | Azure API Management | Kong on AKS | APIM has native AI gateway capabilities (token rate limiting, semantic caching for Azure OpenAI), developer portal, and Bicep provisioning. Kong requires self-hosting and plugin management. |
| IaC | Bicep | Terraform | Specified in constraints (Bicep). Bicep has first-class Azure support, no state file management, immediate new API version support. Terraform is better for multi-cloud, but project is Azure-only. |
| Search | Azure AI Search | Elasticsearch on AKS | Azure AI Search has integrated vectorization with Azure OpenAI, managed service, semantic ranking. Elasticsearch requires self-hosting, more complex to operate at scale. |
| CI/CD | GitHub Actions | Azure DevOps Pipelines | GitHub Actions has simpler YAML, better marketplace for community actions, OIDC federation with Azure. Azure DevOps is viable if the org already uses it — both work well. |
## What NOT to Use
| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Express.js (directly) | No architecture, no DI, no guards/interceptors — leads to inconsistent code in multi-service platforms | NestJS (wraps Express under the hood) |
| Mongoose/MongoDB | Cosmos DB with MongoDB API adds compatibility overhead; native NoSQL API is faster, better supported, and has vector search | @azure/cosmos SDK with NoSQL API |
| Redux/Redux Toolkit | Over-engineered for server-state-heavy dashboards. Causes unnecessary boilerplate. | TanStack Query for server state, Zustand for minimal client state |
| AWS Lambda / GCP Functions | Project is Azure-only. Multi-cloud compute adds complexity without benefit. | Azure Functions (Flex Consumption) |
| Kubernetes YAML (raw) | Verbose, error-prone, no templating | Helm charts with values files per environment |
| ARM templates (JSON) | Verbose, hard to read, poor module support | Bicep (compiles to ARM but with clean syntax) |
| Azure DevOps Artifacts | npm registry alternative, but adds lock-in | GitHub Packages or npmjs.com private packages |
| Self-hosted Redis | Operational overhead for patching, HA configuration, backup | Azure Cache for Redis (managed, VNet, geo-replication) |
| JWT-only auth (custom) | Rolling your own auth is a security anti-pattern for enterprise | Entra ID with MSAL.js + managed identity |
| Winston (logging) | Slower than pino, bloated API | pino with Application Insights transport |
| Webpack | Slower builds, complex config | Turbopack (ships with Next.js 16, stable) |
| Create React App | Deprecated, no SSR, no API routes | Next.js 16 |
| Dapr | Adds runtime sidecar complexity. Not needed when using Azure-native SDKs directly for pub/sub, state, secrets. | Direct Azure SDK usage (@azure/service-bus, @azure/keyvault-secrets) |
## Version Compatibility
| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| NestJS 11.x | Node.js 20/22 LTS | Requires Node.js ≥ 20. Uses ESM and TypeScript 5.x decorators. |
| Next.js 16.2 | React 19.2 | Ships with React 19.2. React Compiler support stable. |
| Prisma 6.x | Azure SQL, PostgreSQL | Prisma 6 supports Typed SQL. Azure SQL driver works out-of-box. |
| @azure/cosmos 4.x | Cosmos DB NoSQL API | Hierarchical partition keys, vector search, partial document update. |
| @azure/openai 3.x | Azure OpenAI 2024-12-01-preview+ | Supports GPT-5.x, structured outputs, Responses API. |
| Turborepo | pnpm 9+ | Remote caching, task hashing. Requires pnpm workspaces. |
| Tailwind CSS 4.x | Next.js 16 | Native PostCSS integration, design token variables. |
| Vitest 3.x | TypeScript 5.7 | Native ESM, c8/v8 coverage. Compatible with NestJS testing module. |
## Sources
- **Azure AKS** — https://learn.microsoft.com/en-us/azure/aks/what-is-aks (Updated 2025-06-09) — CNCF-certified, SOC/ISO/PCI compliance verified. HIGH confidence.
- **Azure Cosmos DB** — https://learn.microsoft.com/en-us/azure/cosmos-db/overview (Updated 2026-02-02) — Vector search (DiskANN), hierarchical partition keys, NoSQL API verified. HIGH confidence.
- **Azure API Management** — https://learn.microsoft.com/en-us/azure/api-management/api-management-key-concepts (Updated 2025-10-13) — Premium v2, AI gateway capabilities, workspaces verified. HIGH confidence.
- **Azure Functions** — https://learn.microsoft.com/en-us/azure/azure-functions/functions-overview (Updated 2026-03-15) — Flex Consumption plan recommended, Container Apps hosting verified. HIGH confidence.
- **Azure OpenAI Models** — https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure (Updated 2026-03-14) — GPT-5.4 (March 2026), GPT-5 series, embeddings, fine-tuning models verified. HIGH confidence.
- **Azure AI Content Safety** — https://learn.microsoft.com/en-us/azure/ai-services/content-safety/overview (Updated 2026-01-31) — Prompt Shields, groundedness detection, task adherence verified. HIGH confidence.
- **Azure Service Bus** — https://learn.microsoft.com/en-us/azure/service-bus-messaging/service-bus-messaging-overview (Updated 2026-03-13) — Premium tier, geo-replication, AMQP 1.0 verified. HIGH confidence.
- **Azure Event Hubs** — https://learn.microsoft.com/en-us/azure/event-hubs/event-hubs-about (Updated 2026-01-28) — Kafka compatibility, Schema Registry, Capture verified. HIGH confidence.
- **Azure Key Vault** — https://learn.microsoft.com/en-us/azure/key-vault/general/overview (Updated 2025-12-03) — Premium HSM (FIPS 140-3 Level 3) verified. HIGH confidence.
- **Bicep** — https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/overview (Updated 2026-01-08) — Declarative IaC, module system, what-if operation verified. HIGH confidence.
- **Azure Container Registry** — https://learn.microsoft.com/en-us/azure/container-registry/container-registry-intro (Updated 2026-02-12) — Premium geo-replication, Defender scanning verified. HIGH confidence.
- **NestJS** — https://www.npmjs.com/package/@nestjs/core — Version 11.1.17 verified (npm). 3.7M weekly downloads. HIGH confidence.
- **Next.js** — https://nextjs.org/blog — Version 16.2 (March 18, 2026) verified. React 19.2, Turbopack stable, cache components. HIGH confidence.
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
