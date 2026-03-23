---
phase: 04-tools-data-sources-rag-platform-ai-services
plan: 02
subsystem: services
tags: [tool-calling, jsonschema, subprocess, litellm, sse]

requires:
  - phase: 04-01
    provides: Tool, AgentTool models

provides:
  - ToolExecutor service with JSON Schema validation and subprocess sandbox
  - Tool-calling loop in AgentExecutionService (max 10 iterations)
  - complete_with_tools() method in ModelAbstractionService

affects: [04-05-frontend]

tech-stack:
  added: [jsonschema]
  patterns: [tool-calling loop with iteration cap, subprocess sandbox execution]

key-files:
  created:
    - backend/app/services/tool_executor.py
  modified:
    - backend/app/services/model_abstraction.py
    - backend/app/services/agent_execution.py
    - backend/requirements.txt

key-decisions:
  - "Subprocess-based sandbox for PoC (Docker adapter can be swapped in later)"
  - "Non-streaming complete_with_tools() for tool loop, streaming for final response"
  - "Tools with no execution_command return mock result (stub for platform tools)"

patterns-established:
  - "Tool-calling loop: model requests tool → validate → execute → feed result back"
  - "OpenAI-format tool schemas built from Tool model for LiteLLM compatibility"

requirements-completed: [TOOL-03]

duration: 6min
completed: 2026-03-23
---

# Plan 04-02: Tool Execution Sandbox & Calling Loop Summary

**Built tool execution engine — agents can now invoke tools during conversations with JSON Schema validation, subprocess sandboxing, and automatic result feedback.**

## Performance

- **Tasks:** 2 completed
- **Files created:** 1
- **Files modified:** 3

## Accomplishments
- Created ToolExecutor with JSON Schema input validation and subprocess sandbox with configurable timeout
- Extended ModelAbstractionService with complete_with_tools() for non-streaming tool-aware completions
- Integrated tool-calling loop into AgentExecutionService with max 10 iteration safety cap
- Added jsonschema dependency to requirements.txt

## Task Commits

1. **Task 1: Create ToolExecutor service** - `a99d1a9` (feat)
2. **Task 2: Extend agent execution with tool-calling loop** - `d0b70e8` (feat)

## Files Created/Modified
- `backend/app/services/tool_executor.py` - ToolExecutor with validation, subprocess, timeout
- `backend/app/services/model_abstraction.py` - Added complete_with_tools(), tools param to _build_litellm_params
- `backend/app/services/agent_execution.py` - Tool-calling loop, _load_agent_tools, _build_tool_schemas
- `backend/requirements.txt` - Added jsonschema>=4.23.0

## Deviations from Plan
None - plan executed exactly as written.

## Issues Encountered
None.
