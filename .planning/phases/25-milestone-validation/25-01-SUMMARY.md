---
phase: 25-milestone-validation
plan: 01
subsystem: infra, testing
tags: [cosmos-db, bicep, unique-keys, test-fixtures]

requires:
  - phase: 19-data-layer-migration
    provides: Cosmos DB repository layer and container definitions
provides:
  - uniqueKeyPolicy on 7 Cosmos DB containers for business uniqueness
  - MockCosmosContainer and MockCosmosClient test fixtures
affects: [25-02, 25-03]

tech-stack:
  added: []
  patterns: [mock-cosmos-container, unique-key-policy]

key-files:
  created: []
  modified:
    - infra/modules/cosmos.bicep
    - backend/tests/conftest.py

key-decisions:
  - "Split container loop into two resources: uniqueContainers (7 with uniqueKeyPolicy) and simpleContainers (28 without)"
  - "MockCosmosContainer uses in-memory dict keyed by (partition_key, item_id) for realistic Cosmos behavior"

patterns-established:
  - "Cosmos mock fixtures: use mock_cosmos_client fixture to patch get_cosmos_container for all repository tests"

requirements-completed: [DATA-06]

duration: 5min
completed: 2026-03-26
---

# Phase 25-01: Cosmos DB Unique Keys + Test Fixtures

**Added uniqueKeyPolicy constraints to 7 Cosmos containers and created shared mock fixtures for repository testing.**

## Performance

- **Duration:** 5 min
- **Tasks:** 2 completed
- **Files modified:** 2

## Accomplishments
- DATA-06 gap closed: uniqueKeyPolicy defined on agents, data_sources, mcp_servers, model_endpoints, tenants, tools, users containers
- MockCosmosContainer with ETag concurrency, partition isolation, and full CRUD support
- MockCosmosClient and mock_cosmos_client fixture ready for Plans 25-02 and 25-03

## Task Commits

1. **Task 1: Add uniqueKeyPolicy to Cosmos DB containers** - `103b541` (fix)
2. **Task 2: Create Cosmos DB mock fixtures in conftest.py** - `abcf33c` (test)

## Files Created/Modified
- `infra/modules/cosmos.bicep` - Split into uniqueContainers (7) and simpleContainers (28) with uniqueKeyPolicy
- `backend/tests/conftest.py` - Added MockCosmosContainer, MockCosmosClient, mock_container and mock_cosmos_client fixtures

## Decisions Made
- Split container creation into two Bicep resource loops rather than a single conditional loop for clarity
- MockCosmosContainer implements async generators for query_items to match real Cosmos SDK behavior

## Deviations from Plan
None - plan executed exactly as written
