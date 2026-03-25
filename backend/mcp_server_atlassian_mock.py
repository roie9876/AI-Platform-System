"""
Mock Atlassian (Jira + Confluence) MCP server for demos.

Returns realistic fake data — no real Jira/Confluence instance needed.

Run with:
    cd backend && source .venv/bin/activate && python mcp_server_atlassian_mock.py

Then register in the UI:
    URL: http://localhost:8082/mcp
    Auth: none

Tools provided:
  Jira:
    - jira_search_issues:    Search issues with JQL
    - jira_get_issue:         Get issue details by key
    - jira_create_issue:      Create a new issue
    - jira_update_issue:      Update an existing issue
    - jira_add_comment:       Add a comment to an issue
    - jira_list_projects:     List all projects
    - jira_get_transitions:   Get available status transitions

  Confluence:
    - confluence_search:      Search Confluence content (CQL)
    - confluence_get_page:    Get a page by ID or title
    - confluence_create_page: Create a new page
    - confluence_update_page: Update an existing page
    - confluence_list_spaces: List all spaces
"""

import json
import uuid
import logging
import random
from datetime import datetime, timedelta, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-atlassian-mock")

# ---------------------------------------------------------------------------
# Fake data
# ---------------------------------------------------------------------------
USERS = [
    {"accountId": "u-1", "displayName": "Sarah Chen", "email": "sarah.chen@acme.com"},
    {"accountId": "u-2", "displayName": "Marcus Johnson", "email": "marcus.j@acme.com"},
    {"accountId": "u-3", "displayName": "Priya Patel", "email": "priya.p@acme.com"},
    {"accountId": "u-4", "displayName": "Alex Rivera", "email": "alex.r@acme.com"},
    {"accountId": "u-5", "displayName": "Jordan Kim", "email": "jordan.k@acme.com"},
]

PROJECTS = [
    {"key": "PLAT", "name": "AI Platform", "lead": USERS[0], "type": "software"},
    {"key": "DATA", "name": "Data Pipeline", "lead": USERS[1], "type": "software"},
    {"key": "INFRA", "name": "Infrastructure", "lead": USERS[2], "type": "software"},
    {"key": "ML", "name": "ML Models", "lead": USERS[3], "type": "software"},
]

STATUSES = ["To Do", "In Progress", "In Review", "Done"]
PRIORITIES = ["Highest", "High", "Medium", "Low", "Lowest"]
ISSUE_TYPES = ["Bug", "Story", "Task", "Epic", "Sub-task"]

JIRA_ISSUES = [
    {
        "key": "PLAT-142", "summary": "Implement Azure OpenAI fallback when primary endpoint is unavailable",
        "status": "In Progress", "priority": "High", "type": "Story",
        "assignee": USERS[0], "reporter": USERS[3],
        "description": "When the primary Azure OpenAI endpoint returns 429 or 503, the system should automatically retry with the secondary endpoint configured in model_endpoints table.",
        "labels": ["resilience", "azure", "p1"],
        "sprint": "Sprint 24",
        "story_points": 5,
        "comments": [
            {"author": USERS[3], "body": "Secondary endpoint config is already in the DB, just need the retry logic.", "created": "2026-03-20T10:30:00Z"},
            {"author": USERS[0], "body": "Working on this now. Adding exponential backoff with jitter.", "created": "2026-03-22T14:15:00Z"},
        ],
    },
    {
        "key": "PLAT-143", "summary": "Add cost tracking per MCP tool invocation",
        "status": "To Do", "priority": "Medium", "type": "Story",
        "assignee": USERS[1], "reporter": USERS[0],
        "description": "Track token usage and estimated cost for each MCP tool call. Store in execution_logs and expose via API for the cost dashboard.",
        "labels": ["observability", "cost"],
        "sprint": "Sprint 24",
        "story_points": 3,
        "comments": [],
    },
    {
        "key": "PLAT-138", "summary": "Agent memory exceeds context window for long conversations",
        "status": "In Review", "priority": "Highest", "type": "Bug",
        "assignee": USERS[2], "reporter": USERS[4],
        "description": "When a thread has more than ~50 messages, the agent memory injection pushes the context window over the limit, causing 400 errors from Azure OpenAI.",
        "labels": ["bug", "memory", "critical"],
        "sprint": "Sprint 23",
        "story_points": 8,
        "comments": [
            {"author": USERS[2], "body": "Added sliding window + summarization. PR #287 ready for review.", "created": "2026-03-24T09:00:00Z"},
        ],
    },
    {
        "key": "PLAT-145", "summary": "Marketplace: add rating and review system for shared agents",
        "status": "To Do", "priority": "Medium", "type": "Epic",
        "assignee": None, "reporter": USERS[0],
        "description": "Users should be able to rate (1-5 stars) and leave reviews on agents published to the marketplace. Include moderation workflow.",
        "labels": ["marketplace", "feature"],
        "sprint": None,
        "story_points": 13,
        "comments": [],
    },
    {
        "key": "DATA-89", "summary": "ETL pipeline fails on malformed CSV with UTF-16 encoding",
        "status": "Done", "priority": "High", "type": "Bug",
        "assignee": USERS[1], "reporter": USERS[4],
        "description": "The data ingestion pipeline crashes when processing CSV files with UTF-16 encoding and BOM markers.",
        "labels": ["bug", "data-ingestion"],
        "sprint": "Sprint 23",
        "story_points": 2,
        "comments": [
            {"author": USERS[1], "body": "Fixed in PR #102. Added encoding detection with chardet.", "created": "2026-03-18T16:45:00Z"},
        ],
    },
    {
        "key": "INFRA-201", "summary": "Upgrade PostgreSQL from 15 to 16 in staging",
        "status": "In Progress", "priority": "Medium", "type": "Task",
        "assignee": USERS[2], "reporter": USERS[2],
        "description": "Upgrade the staging PostgreSQL instance to version 16 for improved query performance and logical replication enhancements.",
        "labels": ["infrastructure", "database"],
        "sprint": "Sprint 24",
        "story_points": 3,
        "comments": [],
    },
    {
        "key": "ML-55", "summary": "Fine-tune embedding model for domain-specific RAG",
        "status": "To Do", "priority": "High", "type": "Story",
        "assignee": USERS[3], "reporter": USERS[0],
        "description": "Current generic embeddings have low recall on our domain-specific documents. Fine-tune text-embedding-3-small on our labeled dataset.",
        "labels": ["ml", "rag", "embeddings"],
        "sprint": "Sprint 25",
        "story_points": 8,
        "comments": [],
    },
]

CONFLUENCE_SPACES = [
    {"key": "ENG", "name": "Engineering", "type": "global"},
    {"key": "ARCH", "name": "Architecture Decisions", "type": "global"},
    {"key": "OPS", "name": "Operations Runbooks", "type": "global"},
    {"key": "ONBOARD", "name": "Onboarding", "type": "global"},
]

CONFLUENCE_PAGES = [
    {
        "id": "pg-1001", "title": "AI Platform Architecture Overview",
        "space": "ARCH", "author": USERS[0], "status": "current",
        "body": (
            "<h2>System Architecture</h2>"
            "<p>The AI Platform is a multi-tenant system built with FastAPI (backend) and Next.js (frontend).</p>"
            "<h3>Core Components</h3>"
            "<ul>"
            "<li><strong>Agent Engine</strong> — Orchestrates LLM calls with tool use, memory, and context management</li>"
            "<li><strong>MCP Gateway</strong> — Connects agents to external tools via Model Context Protocol servers</li>"
            "<li><strong>Evaluation Framework</strong> — Automated testing of agent quality with custom metrics</li>"
            "<li><strong>Marketplace</strong> — Share and discover pre-built agents across tenants</li>"
            "</ul>"
            "<h3>Infrastructure</h3>"
            "<p>Deployed on Azure with PostgreSQL (Flexible Server), Azure OpenAI, and Azure Container Apps.</p>"
        ),
        "version": 12, "last_updated": "2026-03-15T10:00:00Z",
    },
    {
        "id": "pg-1002", "title": "MCP Server Integration Guide",
        "space": "ENG", "author": USERS[1], "status": "current",
        "body": (
            "<h2>How to Add an MCP Server</h2>"
            "<p>MCP servers provide tools that agents can invoke during execution.</p>"
            "<h3>Steps</h3>"
            "<ol>"
            "<li>Register the MCP server URL via the API or UI</li>"
            "<li>Run tool discovery to detect available tools</li>"
            "<li>Attach discovered tools to specific agents</li>"
            "<li>The agent's LLM will automatically select the right tool based on context</li>"
            "</ol>"
            "<h3>Supported Transports</h3>"
            "<p>Currently supports HTTP+JSON-RPC (Streamable HTTP). SSE transport planned for v2.</p>"
        ),
        "version": 5, "last_updated": "2026-03-20T14:30:00Z",
    },
    {
        "id": "pg-1003", "title": "Incident Response Runbook",
        "space": "OPS", "author": USERS[2], "status": "current",
        "body": (
            "<h2>Incident Response Process</h2>"
            "<h3>Severity Levels</h3>"
            "<ul>"
            "<li><strong>SEV1</strong> — Platform down, all tenants affected</li>"
            "<li><strong>SEV2</strong> — Major feature unavailable, workaround exists</li>"
            "<li><strong>SEV3</strong> — Minor issue, limited impact</li>"
            "</ul>"
            "<h3>On-Call Rotation</h3>"
            "<p>See PagerDuty schedule. Escalation after 15 min for SEV1, 30 min for SEV2.</p>"
        ),
        "version": 8, "last_updated": "2026-03-10T09:00:00Z",
    },
    {
        "id": "pg-1004", "title": "New Developer Onboarding Checklist",
        "space": "ONBOARD", "author": USERS[4], "status": "current",
        "body": (
            "<h2>Welcome! 🎉</h2>"
            "<p>Complete these steps in your first week:</p>"
            "<ol>"
            "<li>Set up local dev environment (see README.md)</li>"
            "<li>Get Azure subscription access from IT</li>"
            "<li>Join #engineering and #incidents Slack channels</li>"
            "<li>Complete security training in LMS</li>"
            "<li>Shadow on-call engineer for one shift</li>"
            "<li>Deploy a test change to staging</li>"
            "</ol>"
        ),
        "version": 3, "last_updated": "2026-02-28T11:00:00Z",
    },
    {
        "id": "pg-1005", "title": "ADR-007: Choosing MCP over Custom Tool Protocol",
        "space": "ARCH", "author": USERS[0], "status": "current",
        "body": (
            "<h2>Context</h2>"
            "<p>We need a standard protocol for agents to invoke external tools.</p>"
            "<h2>Decision</h2>"
            "<p>Adopt the Model Context Protocol (MCP) as our tool integration standard.</p>"
            "<h2>Rationale</h2>"
            "<ul>"
            "<li>Open standard with growing ecosystem</li>"
            "<li>Built-in tool discovery via tools/list</li>"
            "<li>Supports multiple transports (stdio, SSE, HTTP)</li>"
            "<li>Reduces vendor lock-in vs proprietary tool APIs</li>"
            "</ul>"
            "<h2>Consequences</h2>"
            "<p>All new tool integrations must be wrapped as MCP servers.</p>"
        ),
        "version": 2, "last_updated": "2026-03-01T16:00:00Z",
    },
]

# Auto-increment counters for created items
_next_issue_num = {"PLAT": 146, "DATA": 90, "INFRA": 202, "ML": 56}
_next_page_id = 1006


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Tool definitions (JSON Schema)
# ---------------------------------------------------------------------------
TOOLS = [
    # --- Jira Tools ---
    {
        "name": "jira_search_issues",
        "description": "Search Jira issues using JQL (Jira Query Language). Returns matching issues with key, summary, status, assignee, and priority. Examples: 'project = PLAT AND status = \"In Progress\"', 'assignee = currentUser() AND sprint in openSprints()', 'labels = bug AND priority = High'.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "jql": {"type": "string", "description": "JQL query string"},
                "max_results": {"type": "integer", "description": "Max results (default: 10)", "default": 10},
            },
            "required": ["jql"],
        },
    },
    {
        "name": "jira_get_issue",
        "description": "Get full details of a Jira issue by its key (e.g., PLAT-142). Returns summary, description, status, assignee, comments, and more.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "issue_key": {"type": "string", "description": "Issue key, e.g. PLAT-142"},
            },
            "required": ["issue_key"],
        },
    },
    {
        "name": "jira_create_issue",
        "description": "Create a new Jira issue. Returns the created issue key.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_key": {"type": "string", "description": "Project key (e.g., PLAT)"},
                "summary": {"type": "string", "description": "Issue title/summary"},
                "issue_type": {"type": "string", "description": "Type: Bug, Story, Task, Epic", "default": "Task"},
                "description": {"type": "string", "description": "Detailed description"},
                "priority": {"type": "string", "description": "Priority: Highest, High, Medium, Low, Lowest", "default": "Medium"},
                "assignee_email": {"type": "string", "description": "Assignee email address (optional)"},
                "labels": {"type": "array", "items": {"type": "string"}, "description": "Labels to apply"},
            },
            "required": ["project_key", "summary"],
        },
    },
    {
        "name": "jira_update_issue",
        "description": "Update fields on an existing Jira issue (summary, description, status, priority, assignee, labels).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "issue_key": {"type": "string", "description": "Issue key, e.g. PLAT-142"},
                "summary": {"type": "string", "description": "New summary (optional)"},
                "description": {"type": "string", "description": "New description (optional)"},
                "status": {"type": "string", "description": "New status (optional)"},
                "priority": {"type": "string", "description": "New priority (optional)"},
                "assignee_email": {"type": "string", "description": "New assignee email (optional)"},
                "labels": {"type": "array", "items": {"type": "string"}, "description": "Replace labels (optional)"},
            },
            "required": ["issue_key"],
        },
    },
    {
        "name": "jira_add_comment",
        "description": "Add a comment to a Jira issue.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "issue_key": {"type": "string", "description": "Issue key, e.g. PLAT-142"},
                "body": {"type": "string", "description": "Comment text (supports markdown)"},
            },
            "required": ["issue_key", "body"],
        },
    },
    {
        "name": "jira_list_projects",
        "description": "List all Jira projects the user has access to.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "jira_get_transitions",
        "description": "Get available status transitions for an issue (e.g., To Do → In Progress → In Review → Done).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "issue_key": {"type": "string", "description": "Issue key, e.g. PLAT-142"},
            },
            "required": ["issue_key"],
        },
    },
    # --- Confluence Tools ---
    {
        "name": "confluence_search",
        "description": "Search Confluence pages using CQL (Confluence Query Language) or text. Examples: 'space = ENG AND title ~ \"architecture\"', 'text ~ \"deployment guide\"', 'label = runbook'.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "CQL query or search text"},
                "max_results": {"type": "integer", "description": "Max results (default: 10)", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "confluence_get_page",
        "description": "Get a Confluence page by ID or title. Returns title, body content, space, version, and metadata.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "page_id": {"type": "string", "description": "Page ID (optional if title provided)"},
                "title": {"type": "string", "description": "Page title (optional if page_id provided)"},
                "space_key": {"type": "string", "description": "Space key to narrow title search (optional)"},
            },
        },
    },
    {
        "name": "confluence_create_page",
        "description": "Create a new Confluence page in a space.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "space_key": {"type": "string", "description": "Space key (e.g., ENG)"},
                "title": {"type": "string", "description": "Page title"},
                "body": {"type": "string", "description": "Page content (HTML or plain text)"},
                "parent_page_id": {"type": "string", "description": "Parent page ID (optional)"},
            },
            "required": ["space_key", "title", "body"],
        },
    },
    {
        "name": "confluence_update_page",
        "description": "Update an existing Confluence page's title or content.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "page_id": {"type": "string", "description": "Page ID to update"},
                "title": {"type": "string", "description": "New title (optional)"},
                "body": {"type": "string", "description": "New body content (optional)"},
            },
            "required": ["page_id"],
        },
    },
    {
        "name": "confluence_list_spaces",
        "description": "List all Confluence spaces the user has access to.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def _match_jql(issue, jql):
    """JQL-like matching that handles common LLM-generated queries.

    Supports AND clauses, currentUser(), openSprints(), resolution = Unresolved,
    ORDER BY (ignored), and falls back to text search.
    """
    jql_lower = jql.lower()
    if not jql.strip():
        return True

    # Strip ORDER BY clause — not relevant for filtering
    if "order by" in jql_lower:
        jql_lower = jql_lower[:jql_lower.index("order by")].strip()
    if not jql_lower:
        return True

    # Split on AND — ALL clauses must match
    clauses = [c.strip() for c in jql_lower.replace(" and ", " AND ").split(" AND ")]
    clauses = [c for c in clauses if c]

    for clause in clauses:
        if not _match_clause(issue, clause):
            return False
    return True


def _match_clause(issue, clause):
    """Match a single JQL clause against an issue."""

    # --- assignee = currentUser() → treat as "has an assignee" (demo user) ---
    if "currentuser()" in clause and "assignee" in clause:
        return issue["assignee"] is not None

    # --- assignee = Unassigned or assignee is EMPTY ---
    if "assignee" in clause and ("unassigned" in clause or "empty" in clause):
        return issue["assignee"] is None

    # --- resolution = Unresolved → not Done ---
    if "resolution" in clause and "unresolved" in clause:
        return issue["status"] != "Done"

    # --- resolution = Done/Resolved → Done ---
    if "resolution" in clause and ("done" in clause or "resolved" in clause):
        return issue["status"] == "Done"

    # --- sprint in openSprints() → has a sprint assigned ---
    if "opensprint" in clause or "opensprints()" in clause:
        return issue.get("sprint") is not None

    # --- project = X ---
    if "project" in clause:
        for proj in PROJECTS:
            if proj["key"].lower() in clause:
                return issue["key"].startswith(proj["key"])
        return False

    # --- status = X or status != X ---
    if "status" in clause:
        negate = "!=" in clause or "not" in clause
        for status in STATUSES:
            if status.lower() in clause:
                match = issue["status"].lower() == status.lower()
                return (not match) if negate else match
        return False

    # --- priority = X ---
    if "priority" in clause:
        for pri in PRIORITIES:
            if pri.lower() in clause:
                return issue["priority"].lower() == pri.lower()
        return False

    # --- issuetype = X or type = X ---
    if "issuetype" in clause or "type" in clause:
        for itype in ISSUE_TYPES:
            if itype.lower() in clause:
                return issue["type"].lower() == itype.lower()
        return False

    # --- labels = X or label = X ---
    if "label" in clause:
        for label in issue.get("labels", []):
            if label.lower() in clause:
                return True
        return False

    # --- assignee = "Name" ---
    if "assignee" in clause:
        if issue["assignee"]:
            name = issue["assignee"]["displayName"].lower()
            if any(part in clause for part in name.split()):
                return True
        return False

    # --- text ~ "something" or summary ~ "something" ---
    if "~" in clause:
        # Extract the search term after ~
        parts = clause.split("~")
        if len(parts) == 2:
            term = parts[1].strip().strip('"\'').lower()
            searchable = f"{issue['key']} {issue['summary']} {issue.get('description', '')}".lower()
            return term in searchable

    # --- Fallback: any significant word matches issue text ---
    searchable = f"{issue['key']} {issue['summary']} {issue.get('description', '')}".lower()
    words = [w.strip('"\'()') for w in clause.split()
             if len(w) > 2 and w not in ("and", "or", "not", "in", "the", "is")]
    return any(w in searchable for w in words) if words else True


def _format_issue_summary(issue):
    assignee = issue["assignee"]["displayName"] if issue["assignee"] else "Unassigned"
    return (
        f"[{issue['key']}] {issue['summary']}\n"
        f"  Status: {issue['status']} | Priority: {issue['priority']} | Type: {issue['type']}\n"
        f"  Assignee: {assignee}"
    )


def _format_issue_detail(issue):
    assignee = issue["assignee"]["displayName"] if issue["assignee"] else "Unassigned"
    reporter = issue["reporter"]["displayName"]
    labels = ", ".join(issue.get("labels", [])) or "None"
    sprint = issue.get("sprint") or "Backlog"
    points = issue.get("story_points", "–")

    lines = [
        f"{'='*60}",
        f"{issue['key']}: {issue['summary']}",
        f"{'='*60}",
        f"Type:         {issue['type']}",
        f"Status:       {issue['status']}",
        f"Priority:     {issue['priority']}",
        f"Assignee:     {assignee}",
        f"Reporter:     {reporter}",
        f"Labels:       {labels}",
        f"Sprint:       {sprint}",
        f"Story Points: {points}",
        f"",
        f"Description:",
        f"  {issue.get('description', 'No description')}",
    ]

    comments = issue.get("comments", [])
    if comments:
        lines.append(f"\nComments ({len(comments)}):")
        for c in comments:
            lines.append(f"  [{c['created']}] {c['author']['displayName']}:")
            lines.append(f"    {c['body']}")

    return "\n".join(lines)


def execute_tool(name, arguments):
    global _next_page_id
    try:
        # --- Jira ---
        if name == "jira_search_issues":
            jql = arguments.get("jql", "")
            max_results = arguments.get("max_results", 10)
            matches = [i for i in JIRA_ISSUES if _match_jql(i, jql)][:max_results]
            if not matches:
                return {"text": f"No issues found matching: {jql}"}
            header = f"Found {len(matches)} issue(s) matching: {jql}\n\n"
            return {"text": header + "\n\n".join(_format_issue_summary(i) for i in matches)}

        if name == "jira_get_issue":
            key = arguments.get("issue_key", "").upper()
            issue = next((i for i in JIRA_ISSUES if i["key"] == key), None)
            if not issue:
                return {"error": f"Issue {key} not found"}
            return {"text": _format_issue_detail(issue)}

        if name == "jira_create_issue":
            proj = arguments.get("project_key", "PLAT").upper()
            if proj not in _next_issue_num:
                return {"error": f"Project {proj} not found"}
            num = _next_issue_num[proj]
            _next_issue_num[proj] += 1
            new_key = f"{proj}-{num}"
            assignee = None
            if arguments.get("assignee_email"):
                assignee = next((u for u in USERS if u["email"] == arguments["assignee_email"]), USERS[0])
            new_issue = {
                "key": new_key,
                "summary": arguments.get("summary", "New issue"),
                "status": "To Do",
                "priority": arguments.get("priority", "Medium"),
                "type": arguments.get("issue_type", "Task"),
                "assignee": assignee,
                "reporter": USERS[0],
                "description": arguments.get("description", ""),
                "labels": arguments.get("labels", []),
                "sprint": None,
                "story_points": None,
                "comments": [],
            }
            JIRA_ISSUES.append(new_issue)
            return {"text": f"✅ Created issue {new_key}: {new_issue['summary']}\n\nURL: https://acme.atlassian.net/browse/{new_key}"}

        if name == "jira_update_issue":
            key = arguments.get("issue_key", "").upper()
            issue = next((i for i in JIRA_ISSUES if i["key"] == key), None)
            if not issue:
                return {"error": f"Issue {key} not found"}
            changes = []
            for field in ("summary", "description", "status", "priority", "labels"):
                if field in arguments and arguments[field] is not None:
                    old_val = issue[field]
                    issue[field] = arguments[field]
                    changes.append(f"  {field}: {old_val} → {arguments[field]}")
            if arguments.get("assignee_email"):
                user = next((u for u in USERS if u["email"] == arguments["assignee_email"]), None)
                if user:
                    issue["assignee"] = user
                    changes.append(f"  assignee → {user['displayName']}")
            if not changes:
                return {"text": f"No changes applied to {key}."}
            return {"text": f"✅ Updated {key}:\n" + "\n".join(changes)}

        if name == "jira_add_comment":
            key = arguments.get("issue_key", "").upper()
            issue = next((i for i in JIRA_ISSUES if i["key"] == key), None)
            if not issue:
                return {"error": f"Issue {key} not found"}
            comment = {
                "author": USERS[0],
                "body": arguments.get("body", ""),
                "created": _now_iso(),
            }
            issue["comments"].append(comment)
            return {"text": f"✅ Comment added to {key} by {comment['author']['displayName']}."}

        if name == "jira_list_projects":
            lines = ["Jira Projects:\n"]
            for p in PROJECTS:
                lines.append(f"  [{p['key']}] {p['name']} (Lead: {p['lead']['displayName']})")
            return {"text": "\n".join(lines)}

        if name == "jira_get_transitions":
            key = arguments.get("issue_key", "").upper()
            issue = next((i for i in JIRA_ISSUES if i["key"] == key), None)
            if not issue:
                return {"error": f"Issue {key} not found"}
            current = issue["status"]
            idx = STATUSES.index(current) if current in STATUSES else 0
            available = [s for s in STATUSES if s != current]
            lines = [f"Current status: {current}", f"Available transitions:"]
            for s in available:
                lines.append(f"  → {s}")
            return {"text": "\n".join(lines)}

        # --- Confluence ---
        if name == "confluence_search":
            query = arguments.get("query", "").lower()
            max_results = arguments.get("max_results", 10)
            matches = []
            for page in CONFLUENCE_PAGES:
                searchable = f"{page['title']} {page['body']} {page['space']}".lower()
                if any(w in searchable for w in query.split() if len(w) > 2):
                    matches.append(page)
            matches = matches[:max_results]
            if not matches:
                return {"text": f"No Confluence pages found matching: {query}"}
            lines = [f"Found {len(matches)} page(s):\n"]
            for p in matches:
                lines.append(f"  [{p['space']}] {p['title']} (id: {p['id']}, v{p['version']})")
                lines.append(f"    Last updated: {p['last_updated']} by {p['author']['displayName']}")
            return {"text": "\n".join(lines)}

        if name == "confluence_get_page":
            page = None
            if arguments.get("page_id"):
                page = next((p for p in CONFLUENCE_PAGES if p["id"] == arguments["page_id"]), None)
            elif arguments.get("title"):
                title_lower = arguments["title"].lower()
                space = arguments.get("space_key", "").upper()
                for p in CONFLUENCE_PAGES:
                    if title_lower in p["title"].lower():
                        if not space or p["space"] == space:
                            page = p
                            break
            if not page:
                return {"error": "Page not found"}
            # Strip HTML tags for readable output
            import re
            clean_body = re.sub(r"<[^>]+>", "", page["body"])
            clean_body = re.sub(r"\n{3,}", "\n\n", clean_body)
            return {
                "text": (
                    f"{'='*60}\n"
                    f"{page['title']}\n"
                    f"{'='*60}\n"
                    f"Space: {page['space']} | Version: {page['version']}\n"
                    f"Author: {page['author']['displayName']}\n"
                    f"Last Updated: {page['last_updated']}\n"
                    f"\n{clean_body.strip()}"
                )
            }

        if name == "confluence_create_page":
            page_id = f"pg-{_next_page_id}"
            _next_page_id += 1
            new_page = {
                "id": page_id,
                "title": arguments.get("title", "Untitled"),
                "space": arguments.get("space_key", "ENG").upper(),
                "author": USERS[0],
                "status": "current",
                "body": arguments.get("body", ""),
                "version": 1,
                "last_updated": _now_iso(),
            }
            CONFLUENCE_PAGES.append(new_page)
            space_name = next((s["name"] for s in CONFLUENCE_SPACES if s["key"] == new_page["space"]), new_page["space"])
            return {
                "text": (
                    f"✅ Created Confluence page:\n"
                    f"  Title: {new_page['title']}\n"
                    f"  Space: {space_name}\n"
                    f"  ID: {page_id}\n"
                    f"  URL: https://acme.atlassian.net/wiki/spaces/{new_page['space']}/pages/{page_id}"
                )
            }

        if name == "confluence_update_page":
            page_id = arguments.get("page_id", "")
            page = next((p for p in CONFLUENCE_PAGES if p["id"] == page_id), None)
            if not page:
                return {"error": f"Page {page_id} not found"}
            changes = []
            if arguments.get("title"):
                page["title"] = arguments["title"]
                changes.append(f"  title → {arguments['title']}")
            if arguments.get("body"):
                page["body"] = arguments["body"]
                changes.append("  body → (updated)")
            page["version"] += 1
            page["last_updated"] = _now_iso()
            if not changes:
                return {"text": f"No changes applied to page {page_id}."}
            return {"text": f"✅ Updated page {page_id} (now v{page['version']}):\n" + "\n".join(changes)}

        if name == "confluence_list_spaces":
            lines = ["Confluence Spaces:\n"]
            for s in CONFLUENCE_SPACES:
                lines.append(f"  [{s['key']}] {s['name']} ({s['type']})")
            return {"text": "\n".join(lines)}

        return {"error": f"Unknown tool: {name}"}

    except Exception as e:
        logger.error(f"Tool {name} failed: {e}", exc_info=True)
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# JSON-RPC 2.0 handler
# ---------------------------------------------------------------------------
def handle_jsonrpc(body):
    method = body.get("method", "")
    req_id = body.get("id")
    params = body.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "Atlassian Mock MCP Server", "version": "1.0.0"},
                "capabilities": {"tools": {"listChanged": False}},
            },
        }

    if method == "notifications/initialized":
        return None

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": TOOLS},
        }

    if method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        logger.info("Executing tool: %s with args: %s", tool_name, json.dumps(arguments)[:200])

        result = execute_tool(tool_name, arguments)

        is_error = "error" in result
        text = result.get("error") or result.get("text") or json.dumps(result, indent=2)

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [{"type": "text", "text": text}],
                "isError": is_error,
            },
        }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Unknown method: {method}"},
    }


# ---------------------------------------------------------------------------
# HTTP Server
# ---------------------------------------------------------------------------
class MCPHandler(BaseHTTPRequestHandler):
    session_id = str(uuid.uuid4())

    def do_POST(self):
        if self.path != "/mcp":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        logger.info("← %s", body.get("method", "?"))

        response = handle_jsonrpc(body)

        if response is None:
            self.send_response(202)
            self.send_header("Mcp-Session-Id", self.session_id)
            self.end_headers()
            return

        payload = json.dumps(response).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Mcp-Session-Id", self.session_id)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        logger.debug(fmt % args)


if __name__ == "__main__":
    PORT = 8082
    server = HTTPServer(("0.0.0.0", PORT), MCPHandler)
    logger.info("🚀 Atlassian Mock MCP Server running on http://localhost:%d/mcp", PORT)
    logger.info("Tools: %s", ", ".join(t["name"] for t in TOOLS))
    logger.info("Register in UI → URL: http://localhost:8082/mcp, Auth: none")
    logger.info("")
    logger.info("Demo data: %d Jira issues, %d Confluence pages, %d projects, %d spaces",
                len(JIRA_ISSUES), len(CONFLUENCE_PAGES), len(PROJECTS), len(CONFLUENCE_SPACES))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
