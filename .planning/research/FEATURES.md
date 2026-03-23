# Feature Research

**Domain:** Enterprise AI Platform (model orchestration, deployment, and consumption)
**Researched:** 2026-03-23
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Model Catalog & Discovery** | All three platforms (Foundry, Vertex AI, Bedrock) lead with a searchable model catalog. Users expect to browse, filter by task/provider/modality, and compare models. Bedrock offers 87+ models from 13+ providers; Vertex AI has 200+ models in Model Garden; Foundry has a unified catalog with 1,400+ tools. | MEDIUM | Core value prop — first thing users see. Need model cards with metadata (params, license, benchmarks, pricing). |
| **One-Click Model Deployment** | Deploying a model to a managed endpoint with minimal config is the core workflow. All platforms provide this. Users expect serverless/provisioned options. | HIGH | Bedrock is fully serverless; Vertex AI offers serverless + dedicated endpoints; Foundry uses project-scoped deployments. Must abstract infrastructure (AKS, GPU provisioning). |
| **Standardized API for Model Consumption** | Users expect a consistent API regardless of underlying model provider. Foundry unifies under `/openai/v1/` routes; Bedrock uses `InvokeModel` API; Vertex AI uses Gemini API + prediction endpoints. | HIGH | Critical differentiator opportunity — PROJECT.md identifies "unified consumption API" as key. REST required, gRPC nice-to-have. Must support streaming. |
| **Authentication & RBAC** | Enterprise-grade identity management is non-negotiable. Foundry uses Azure Entra ID with RBAC per resource; Vertex AI uses GCP IAM; Bedrock uses AWS IAM with resource-based policies. | HIGH | Azure Entra ID integration already decided per constraints. Need project-level, team-level, and resource-level access control. |
| **Project/Workspace Organization** | All platforms organize work into projects. Foundry has Foundry resources with projects; Vertex AI has GCP projects; Bedrock works at the AWS account level. Team-scoped isolation is expected. | MEDIUM | Maps to multi-tenancy. Each project needs isolated deployments, API keys, cost tracking, and member management. |
| **Content Safety / Guardrails** | All platforms ship with content filtering. Azure has 4-category content filters (hate, sexual, violence, self-harm) with severity levels. Bedrock Guardrails has 6 policies (content filters, denied topics, word filters, PII redaction, grounding checks, automated reasoning). Vertex AI has Model Armor. | HIGH | Regulatory requirement for enterprise. Need configurable filters on both input (prompts) and output (completions). PII detection/redaction is expected. |
| **Prompt Playground / Studio** | Interactive prompt testing is universal. Foundry has the portal playground; Vertex AI has Vertex AI Studio; Bedrock has a playground in the console. Users expect to test models before deploying. | MEDIUM | Low-code entry point for non-developers. Need chat mode, completion mode, parameter tuning (temperature, top-p, max tokens). |
| **Usage Monitoring & Logging** | Token consumption, latency, error rates, request logs. All platforms provide this. Foundry has real-time observability with tracing; Bedrock has CloudWatch integration; Vertex AI has Model Monitoring. | MEDIUM | Must track per-deployment, per-project, per-user metrics. Store request/response logs for debugging and auditing. |
| **Model Evaluation & Benchmarking** | Comparing model performance before deployment. Bedrock has built-in evaluation tools for model selection; Vertex AI has Gen AI Evaluation Service; Foundry has evaluations with tracing. | MEDIUM | At minimum: automated metrics (latency, throughput, accuracy). Stretch: custom evaluation datasets, A/B testing across models. |
| **SDK & CLI Tooling** | Programmatic access beyond the UI. Foundry offers Python, C#, JS/TS, Java SDKs + VS Code extension; Vertex AI has Python SDK + gcloud CLI; Bedrock has AWS SDK (all languages) + AWS CLI. | MEDIUM | Python SDK is highest priority. CLI for CI/CD integration. OpenAPI spec for generating additional language SDKs. |
| **Cost Tracking & Billing** | Per-project and per-model cost visibility. Foundry bills at the deployment level; Bedrock is pay-per-use; Vertex AI has per-product pricing. Users need to see spend breakdowns. | MEDIUM | Aggregate token usage × per-model pricing. Budgets, alerts, quotas per project/team. |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valuable.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Multi-Provider Model Aggregation** | PROJECT.md identifies this as key differentiator: aggregate models from Azure OpenAI, Hugging Face, open-source providers, and custom models under ONE catalog and ONE API. Foundry is Azure-models-only; Bedrock is AWS-ecosystem; Vertex AI is Google-first. None offer true cross-cloud aggregation. | HIGH | This is the defining competitive advantage. Unified API layer must normalize request/response formats, authentication, and pricing across providers. |
| **Unified API Gateway with Provider Abstraction** | Single endpoint where swapping models requires only changing a model ID, not rewriting code. Bedrock gets closest with `InvokeModel`, but only within AWS models. Our platform would abstract across providers entirely. | HIGH | Build on Azure API Management. Request transformation, response normalization, automatic retry/fallback across providers. Rate limiting per consumer. |
| **AI Pipeline / Multi-Model Orchestration** | Chain multiple models together: text → image, classification → generation, RAG pipelines. Foundry has multi-agent orchestration; Vertex AI has Pipelines; Bedrock has agent workflows. But none make cross-provider chaining first-class. | HIGH | DAG-based pipeline builder. Visual pipeline editor in UI. Each node = model invocation with configurable I/O mapping. Critical for complex enterprise workflows. |
| **Model Fine-Tuning Workflows** | Supervised fine-tuning, PEFT/LoRA tuning. Foundry supports fine-tuning for OpenAI models; Vertex AI has SFT and PEFT; Bedrock offers customization. Differentiate by offering fine-tuning across providers with unified data management. | HIGH | Requires GPU compute orchestration (AKS + GPU node pools). Training data management, experiment tracking, checkpoint management. |
| **Agent Builder Platform** | 2025-2026 is the year of AI agents. Foundry has multi-agent orchestration with tool catalogs (1,400+ tools) and memory. Bedrock has AgentCore (runtime, gateway, memory, identity, observability). Vertex AI has Agent Builder + Agent Development Kit. | HIGH | Agents are the next evolution beyond model APIs. Need: tool registration, memory/context management, multi-step planning, human-in-the-loop. Consider building on open standards (MCP, A2A). |
| **Prompt Management & Versioning** | Version control for prompts, A/B testing prompt variants, prompt templates with variables. Not fully first-class in any platform yet — mostly handled by third-party tools (LangSmith, PromptLayer). | MEDIUM | Differentiate with first-class prompt versioning, template library, prompt analytics (which prompts perform best). Git-like version history. |
| **Data Management for Training & Evaluation** | Upload, version, and manage datasets for fine-tuning and evaluation. Vertex AI has Dataset resources; Bedrock supports S3-based datasets; Foundry integrates with Azure storage. | MEDIUM | Dataset versioning, schema validation, train/test/val splits, integration with evaluation framework. Link datasets to fine-tuning jobs and evaluation runs. |
| **Model A/B Testing & Canary Deployments** | Route percentage of traffic to different model versions. None of the big three make this trivially easy — it's an ops concern. | MEDIUM | Traffic splitting at the API gateway level. Compare metrics across model versions in real-time. Auto-rollback on degradation. |
| **VS Code Extension / IDE Integration** | Foundry has a VS Code extension. Vertex AI integrates with Colab/Workbench notebooks. Developer-centric platforms need IDE presence. | MEDIUM | Browse catalog, deploy models, test prompts, view logs — all from VS Code. Lower barrier to adoption for developers. |
| **Observability & Tracing (LLM-Specific)** | Full request traces showing prompt → model → response → guardrail decision → output. Foundry has built-in tracing; Bedrock has AgentCore observability; Vertex AI has experiments/monitoring. | MEDIUM | LLM-aware tracing: token counts, latency breakdown (queue vs inference), cost per request, guardrail filter events. OpenTelemetry integration. |
| **Marketplace / Model Publishing** | Let users publish and share fine-tuned models or prompt templates within their organization or publicly. Hugging Face Hub is the gold standard. | MEDIUM | Internal model registry with publish/subscribe. Org-scoped sharing. Model cards with evaluation results. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Custom Foundation Model Training** | "We want to train our own LLM from scratch" | Requires massive GPU clusters, months of training, billions in compute cost. Not viable for a platform — that's a research lab activity. PROJECT.md correctly scopes this out. | Offer fine-tuning, LoRA/PEFT, and RAG as customization paths. Partner with providers who train foundation models. |
| **On-Premises Deployment** | Enterprise customers with strict data residency ask for on-prem. | Massively increases complexity: GPU provisioning, networking, infrastructure management. PROJECT.md scopes this out for v1. | Offer Azure sovereign cloud regions, private endpoints, VNet integration, customer-managed keys. Revisit on-prem for v2+ only if demand is proven. |
| **Mobile Native Apps** | "We need iOS/Android apps" | Platform is for developers and ML engineers — they work in browsers and IDEs, not mobile. Mobile adds two more platforms to maintain. PROJECT.md correctly excludes this. | Web-first responsive UI. Mobile-optimized dashboards for monitoring only if needed later. |
| **Build-Your-Own Hardware/Infra Provisioning** | "Let users choose specific GPU SKUs and manage their own clusters" | Exposes infrastructure complexity the platform should abstract. Creates support burden. | Abstract GPU selection behind deployment tier choices (e.g., "Standard", "High-Performance", "GPU-Optimized"). Let the platform optimize resource allocation. |
| **Universal Model Format Converter** | "Convert models between PyTorch, TensorFlow, ONNX, etc." | Model conversion is lossy, fragile, and model-specific. Creates a massive testing surface. | Support standard formats (ONNX, Hugging Face Transformers). Use pre-built containers per framework rather than converting. |
| **Real-Time Collaborative Model Training** | "Multiple data scientists training the same model simultaneously" | Distributed training is already hard; adding real-time collaboration on top creates coordination nightmares. | Offer experiment tracking with branching. Let teams run parallel experiments and compare results rather than co-editing training runs. |
| **No-Code/Low-Code Model Building** | "Drag-and-drop ML model creation for business users" | This is AutoML territory — extremely complex to do well, and undermines the developer/ML engineer focus. Google and Azure have invested billions and it's still niche. | Offer a great prompt playground and prompt template library for non-technical users. Focus the platform on developers and ML engineers. |
| **Embedding a Full Notebook Environment** | "Built-in Jupyter notebooks for data science" | Massive scope: need compute management, kernel lifecycle, package management, file system. Vertex AI and SageMaker invest dedicated teams in this. | Integrate with existing notebook environments (VS Code, JupyterHub, Colab) via SDK. Don't rebuild what exists. |

## Feature Dependencies

```
[Auth & RBAC]
    └──requires──> [Project/Workspace Organization]
                       └──requires──> [Multi-Tenancy Infrastructure]

[Model Catalog & Discovery]
    └──requires──> [Model Metadata Schema]
    └──enables──> [One-Click Model Deployment]
                       └──requires──> [Compute Orchestration (AKS)]
                       └──requires──> [Auth & RBAC]

[Standardized API Gateway]
    └──requires──> [Model Deployment]
    └──requires──> [Auth & RBAC]
    └──enables──> [Multi-Provider Aggregation]
    └──enables──> [AI Pipeline Orchestration]
    └──enables──> [Model A/B Testing]

[Content Safety / Guardrails]
    └──requires──> [API Gateway] (filters applied at gateway layer)
    └──enhances──> [Model Deployment]

[Prompt Playground]
    └──requires──> [API Gateway]
    └──requires──> [Model Deployment]
    └──enhances──> [Prompt Management & Versioning]

[Usage Monitoring & Logging]
    └──requires──> [API Gateway] (metrics emitted from gateway)
    └──enables──> [Cost Tracking & Billing]

[Model Evaluation]
    └──requires──> [Data Management]
    └──requires──> [Model Deployment]
    └──enhances──> [Model Catalog] (results shown in catalog)

[Fine-Tuning Workflows]
    └──requires──> [Data Management]
    └──requires──> [Compute Orchestration (GPU)]
    └──requires──> [Model Catalog] (base models)
    └──enables──> [Marketplace / Model Publishing]

[Agent Builder]
    └──requires──> [API Gateway]
    └──requires──> [Model Deployment]
    └──requires──> [Auth & RBAC]
    └──enhances──> [AI Pipeline Orchestration]
```

### Dependency Notes

- **API Gateway requires Model Deployment:** You can't route requests without deployed model endpoints to route to.
- **Content Safety requires API Gateway:** Guardrails are applied as middleware in the API request/response pipeline.
- **Cost Tracking requires Usage Monitoring:** Billing is derived from usage telemetry (tokens consumed × pricing).
- **Fine-Tuning requires Data Management:** Training data must be uploaded, validated, and versioned before training jobs can run.
- **Agent Builder requires API Gateway + Model Deployment:** Agents orchestrate calls to deployed models through the API layer.
- **Multi-Provider Aggregation requires Standardized API:** The unified API is what makes multi-provider transparent to consumers.

## MVP Definition

### Launch With (v1)

Minimum viable product — validate the core value proposition of unified multi-provider AI consumption.

- [ ] **Auth & RBAC (Azure Entra ID)** — Foundation for everything else. Gate access to all resources.
- [ ] **Project/Workspace Organization** — Multi-tenant isolation for teams and projects.
- [ ] **Model Catalog & Discovery** — Browse and search models from Azure OpenAI + at least one additional provider (e.g., Hugging Face open models).
- [ ] **One-Click Model Deployment** — Deploy models to managed endpoints on Azure (AKS-backed).
- [ ] **Standardized API Gateway** — Unified REST API for consuming any deployed model regardless of provider. This IS the differentiator.
- [ ] **Content Safety / Guardrails** — Configurable content filters on input/output. At minimum: harmful content blocking + PII detection.
- [ ] **Prompt Playground** — Interactive UI for testing deployed models with parameter tuning.
- [ ] **Usage Monitoring & Logging** — Track requests, tokens, latency, errors per deployment and project.
- [ ] **Cost Tracking** — Token-based usage aggregation with per-project cost visibility.
- [ ] **SDK (Python)** — Programmatic access for developers. Python first.

### Add After Validation (v1.x)

Features to add once core workflow is proven.

- [ ] **Model Evaluation & Benchmarking** — Add when users are deploying multiple models and need to compare.
- [ ] **Prompt Management & Versioning** — Add when users are iterating on prompts and need version history.
- [ ] **Model A/B Testing** — Add when users need to compare model performance on live traffic.
- [ ] **Additional SDKs (C#, TypeScript)** — Expand SDK coverage based on user demand.
- [ ] **CLI Tooling** — Add for CI/CD integration and power users.
- [ ] **Observability & Tracing** — Deep LLM-aware tracing for debugging complex pipelines.
- [ ] **Data Management** — Dataset upload/versioning for fine-tuning and evaluation preparation.
- [ ] **VS Code Extension** — IDE integration for developer-centric workflow.

### Future Consideration (v2+)

Features to defer until product-market fit is established.

- [ ] **Fine-Tuning Workflows** — Complex GPU orchestration; defer until data management and evaluation are solid.
- [ ] **AI Pipeline / Multi-Model Orchestration** — High complexity; needs mature API gateway and multiple deployed models.
- [ ] **Agent Builder Platform** — Rapidly evolving space (MCP, A2A standards still maturing). Build after core platform is stable.
- [ ] **Marketplace / Model Publishing** — Needs community/user base to be valuable. Defer until organic demand.
- [ ] **Multi-Cloud Model Aggregation** — Cross-cloud (GCP, AWS models via Azure) is v2+ ambition once Azure-native aggregation is proven.

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Auth & RBAC (Entra ID) | HIGH | HIGH | P1 |
| Project/Workspace Organization | HIGH | MEDIUM | P1 |
| Model Catalog & Discovery | HIGH | MEDIUM | P1 |
| One-Click Model Deployment | HIGH | HIGH | P1 |
| Standardized API Gateway | HIGH | HIGH | P1 |
| Content Safety / Guardrails | HIGH | HIGH | P1 |
| Prompt Playground | HIGH | MEDIUM | P1 |
| Usage Monitoring & Logging | HIGH | MEDIUM | P1 |
| Cost Tracking & Billing | MEDIUM | MEDIUM | P1 |
| SDK (Python) | HIGH | MEDIUM | P1 |
| Model Evaluation & Benchmarking | MEDIUM | MEDIUM | P2 |
| Prompt Management & Versioning | MEDIUM | LOW | P2 |
| Model A/B Testing | MEDIUM | MEDIUM | P2 |
| Additional SDKs (C#, TS) | MEDIUM | MEDIUM | P2 |
| CLI Tooling | MEDIUM | LOW | P2 |
| LLM Observability & Tracing | MEDIUM | MEDIUM | P2 |
| Data Management | MEDIUM | MEDIUM | P2 |
| VS Code Extension | MEDIUM | MEDIUM | P2 |
| Fine-Tuning Workflows | HIGH | HIGH | P3 |
| AI Pipeline Orchestration | HIGH | HIGH | P3 |
| Agent Builder Platform | HIGH | HIGH | P3 |
| Marketplace / Publishing | LOW | MEDIUM | P3 |
| Multi-Cloud Aggregation | MEDIUM | HIGH | P3 |

**Priority key:**
- P1: Must have for launch — validates core value proposition
- P2: Should have — add after v1 validation, strengthens platform
- P3: Future consideration — high value but high complexity, defer

## Competitor Feature Analysis

| Feature | Azure AI Foundry (now Microsoft Foundry) | Google Vertex AI | AWS Bedrock | Hugging Face | Our Platform |
|---------|------------------------------------------|-----------------|-------------|--------------|--------------|
| Model Catalog | Azure/OpenAI models + some partners | 200+ models (Google + partners + OSS) | 87+ models from 13+ providers | 2M+ open-source models | Multi-provider aggregation (key differentiator) |
| Deployment | Project-scoped, managed | Serverless + dedicated endpoints | Fully serverless, on-demand | Inference Endpoints + Spaces | AKS-backed managed endpoints |
| API Consistency | Unified under `/openai/v1/` routes | Multiple APIs (Gemini, Prediction) | `InvokeModel` unified API | Inference API per model | Single unified REST API across all providers |
| Content Safety | 4-category filters + prompt shields + PII | Model Armor + safety features | 6-policy Guardrails (industry-leading breadth) | Community-driven model cards | Configurable multi-layer guardrails |
| Fine-Tuning | SFT for OpenAI models | SFT + PEFT/LoRA + custom training | Model customization | Full training infrastructure | Unified fine-tuning across providers (v2) |
| Agents | Multi-agent orchestration, 1,400+ tools, memory | Agent Builder + ADK + Agent Engine | AgentCore (Runtime, Gateway, Memory, Identity) | No built-in agent platform | Agent builder with open standards (v2+) |
| Evaluation | Tracing-based evaluations | Gen AI Evaluation Service | Built-in model evaluation tools | Community benchmarks | Integrated evaluation framework |
| Prompt Tools | Portal playground | Vertex AI Studio | Console playground | No built-in | Playground + prompt versioning |
| MLOps | Basic (tracing, monitoring) | Full MLOps suite (Pipelines, Registry, Feature Store, Monitoring) | Basic (CloudWatch) | Basic | Monitoring + logging, MLOps in v2 |
| SDK Languages | Python, C#, JS/TS (preview), Java (preview) | Python, Java, Node.js, Go | All AWS SDK languages | Python (transformers, datasets) | Python (v1), C#/TS (v1.x) |
| Pricing Model | Per-deployment consumption | Per-product (complex) | Pay-per-token (simple) | Per-endpoint hour | Per-token with project budgets |
| Lock-In Risk | Azure ecosystem | GCP ecosystem | AWS ecosystem | None (open source) | Azure-native but provider-agnostic API |

### Key Competitive Observations

1. **Microsoft Foundry** (rebranded from Azure AI Foundry, March 2026) is evolving rapidly — it now has a unified project client SDK (`azure-ai-projects 2.x`) and unified resource model. Biggest weakness: still Azure-models-centric despite multi-provider rhetoric.

2. **Google Vertex AI** has the broadest MLOps tooling (Pipelines, Feature Store, Model Registry, Experiments, Model Monitoring). Strongest for organizations already doing traditional ML alongside GenAI.

3. **AWS Bedrock** has the simplest consumption model (fully serverless, pay-per-token) and leads in guardrails sophistication with Automated Reasoning checks. Broadest model provider selection among incumbents (13+ providers).

4. **Hugging Face** dominates open-source model discovery (2M+ models) but lacks enterprise orchestration, deployment management, and guardrails. It's a model hub, not a platform.

5. **Opportunity:** No platform truly aggregates across cloud providers with a unified API. Our platform can own this niche — especially for enterprises that use models from multiple providers and want one API, one auth system, one billing view.

## Sources

- Microsoft Foundry overview: https://learn.microsoft.com/en-us/azure/foundry/what-is-foundry (accessed 2026-03-23) — **HIGH confidence**
- Microsoft Foundry content filtering: https://learn.microsoft.com/en-us/azure/foundry-classic/foundry-models/concepts/content-filter — **HIGH confidence**
- Google Vertex AI overview: https://docs.cloud.google.com/vertex-ai/docs/start/introduction-unified-platform (accessed 2026-03-23) — **HIGH confidence**
- Google Vertex AI product page: https://cloud.google.com/vertex-ai (accessed 2026-03-23) — **HIGH confidence**
- Amazon Bedrock features: https://aws.amazon.com/bedrock/features/ (accessed 2026-03-23) — **HIGH confidence**
- Amazon Bedrock model choice: https://aws.amazon.com/bedrock/model-choice/ (accessed 2026-03-23) — **HIGH confidence**
- Amazon Bedrock Guardrails: https://aws.amazon.com/bedrock/guardrails/ (accessed 2026-03-23) — **HIGH confidence**
- Hugging Face Hub: https://huggingface.co/docs/hub/en/index (accessed 2026-03-23) — **HIGH confidence**
