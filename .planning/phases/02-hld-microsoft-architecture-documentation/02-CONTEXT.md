# Phase 2 Context: HLD & Microsoft Architecture Documentation

## Phase Goal
Create comprehensive vendor-agnostic HLD with Mermaid diagrams and Microsoft product-mapped architecture documentation.

## Requirements
- ARCH-01: Vendor-agnostic HLD with Mermaid diagrams
- ARCH-02: Microsoft product-mapped architecture
- ARCH-03: Decision documentation with rationale

## Decisions

### D-01: Single Unified Document
**Status:** Locked
**Decision:** Combine the vendor-agnostic HLD and Microsoft architecture mapping into a single unified document rather than separate documents.
**Rationale:** Easier to present, maintain, and reference. Audience sees the full picture in one place.

### D-02: Presentation-Optimized Diagrams
**Status:** Locked
**Decision:** All Mermaid diagrams must be optimized for large-room presentation — simple, clear, high-level. No dense low-level detail diagrams.
**Rationale:** Document will be presented to a room with many people. Clarity and simplicity are paramount.

### D-03: ADR Format for Decisions
**Status:** Locked
**Decision:** Use Architecture Decision Record (ADR) format for documenting architecture decisions (Status, Context, Decision, Consequences).
**Rationale:** Industry-standard format that clearly captures the "why" behind each decision.

### D-04: Specific Azure Services + SKUs
**Status:** Locked
**Decision:** Map each platform component to a specific Azure service AND recommended SKU (not just service names).
**Rationale:** Provides actionable deployment guidance and enables cost estimation.

### D-05: Include Pricing Tiers
**Status:** Locked
**Decision:** Include ballpark pricing tiers (dev environment vs production ranges) for Azure service mappings.
**Rationale:** Stakeholders in the room need cost context to evaluate the architecture.

### D-06: Inline Technology Comparisons
**Status:** Locked
**Decision:** Include "we chose X over Y because Z" comparisons inline with the architecture sections (in addition to ADRs for major decisions).
**Rationale:** Readers see the reasoning in context, not just in a separate decisions appendix.

## Agent's Discretion

- **Diagram selection:** Agent picks ~4-6 high-impact Mermaid diagrams optimized for presentation (e.g., system overview, data flow, deployment, security boundary)
- **ADR scope:** Agent determines which decisions qualify as "major" and merit full ADR treatment
- **Document structure:** Agent decides section ordering for optimal reading flow and presentation flow
- **SKU recommendations:** Agent selects appropriate Azure SKUs based on the platform's scale and multi-tenant nature

## Deferred Ideas

- Detailed runbook/operations documentation (future phase)
- Cost calculator or interactive pricing tool
- Multi-cloud mapping (AWS/GCP equivalents)

## Prior Context (from Phase 1)

Key decisions carried forward:
- FastAPI + Next.js + PostgreSQL + Redis stack (D-01 from Phase 1)
- Control Plane / Runtime Plane separation (from research)
- Multi-tenant with tenant_id in JWT (D-06 from Phase 1)
- Docker Compose for local dev (D-08 from Phase 1)
- 11 feature categories identified in research (FEATURES.md)
