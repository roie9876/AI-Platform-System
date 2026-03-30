"""
Real Atlassian (Jira + Confluence) MCP server.

Connects to a live Atlassian Cloud instance via REST API.
Credentials come from environment variables (injected from Azure Key Vault).

Run locally:
    export JIRA_BASE_URL=https://roie9876.atlassian.net
    export JIRA_EMAIL=roie9876@gmail.com
    export JIRA_API_TOKEN=<token>
    cd backend && python mcp_server_atlassian.py

Register in the UI:
    URL: http://localhost:8082/mcp
    Auth: none (auth is handled server-side)

Tools provided (13 total):
  Jira (7):
    - jira_search_issues, jira_get_issue, jira_create_issue,
      jira_update_issue, jira_add_comment, jira_list_projects,
      jira_get_transitions
  Confluence (6):
    - confluence_search, confluence_get_page, confluence_create_page,
      confluence_update_page, confluence_list_spaces
"""

import json
import os
import re
import uuid
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Optional
from urllib.parse import quote

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-atlassian")

# ---------------------------------------------------------------------------
# Configuration from environment
# ---------------------------------------------------------------------------
BASE_URL = os.environ.get("JIRA_BASE_URL", "https://roie9876.atlassian.net").rstrip("/")
EMAIL = os.environ.get("JIRA_EMAIL", "roie9876@gmail.com")
API_TOKEN = os.environ.get("JIRA_API_TOKEN", "")

if not API_TOKEN:
    logger.warning("JIRA_API_TOKEN not set — API calls will fail")

AUTH = (EMAIL, API_TOKEN)
TIMEOUT = 30  # seconds


def _jira(method: str, path: str, **kwargs) -> requests.Response:
    """Make authenticated request to Jira REST API."""
    url = f"{BASE_URL}/rest/api/3{path}"
    return requests.request(method, url, auth=AUTH, timeout=TIMEOUT, **kwargs)


def _confluence_v1(method: str, path: str, **kwargs) -> requests.Response:
    """Make authenticated request to Confluence v1 REST API."""
    url = f"{BASE_URL}/wiki/rest/api{path}"
    return requests.request(method, url, auth=AUTH, timeout=TIMEOUT, **kwargs)


def _confluence_v2(method: str, path: str, **kwargs) -> requests.Response:
    """Make authenticated request to Confluence v2 REST API."""
    url = f"{BASE_URL}/wiki/api/v2{path}"
    return requests.request(method, url, auth=AUTH, timeout=TIMEOUT, **kwargs)


# ---------------------------------------------------------------------------
# Tool definitions (same schemas as mock for backward compatibility)
# ---------------------------------------------------------------------------
TOOLS = [
    {
        "name": "jira_search_issues",
        "description": "Search Jira issues using JQL (Jira Query Language). Returns matching issues with key, summary, status, assignee, and priority.",
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
        "description": "Get full details of a Jira issue by its key (e.g., MYS-14). Returns summary, description, status, assignee, comments, and more.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "issue_key": {"type": "string", "description": "Issue key, e.g. MYS-14"},
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
                "project_key": {"type": "string", "description": "Project key (e.g., MYS)"},
                "summary": {"type": "string", "description": "Issue title/summary"},
                "issue_type": {"type": "string", "description": "Issue type name (e.g., Task, Bug, Story, [System] Incident, [System] Service request)", "default": "Task"},
                "description": {"type": "string", "description": "Detailed description (plain text)"},
                "priority": {"type": "string", "description": "Priority: Highest, High, Medium, Low, Lowest", "default": "Medium"},
                "assignee_email": {"type": "string", "description": "Assignee email address (optional)"},
                "labels": {"type": "array", "items": {"type": "string"}, "description": "Labels to apply"},
            },
            "required": ["project_key", "summary"],
        },
    },
    {
        "name": "jira_update_issue",
        "description": "Update fields on an existing Jira issue (summary, description, priority, assignee, labels).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "issue_key": {"type": "string", "description": "Issue key, e.g. MYS-14"},
                "summary": {"type": "string", "description": "New summary (optional)"},
                "description": {"type": "string", "description": "New description (optional)"},
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
                "issue_key": {"type": "string", "description": "Issue key, e.g. MYS-14"},
                "body": {"type": "string", "description": "Comment text"},
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
        "description": "Get available status transitions for an issue.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "issue_key": {"type": "string", "description": "Issue key, e.g. MYS-14"},
            },
            "required": ["issue_key"],
        },
    },
    # --- Confluence Tools ---
    {
        "name": "confluence_search",
        "description": "Search Confluence pages using CQL (Confluence Query Language) or text. Examples: 'space = ITKB AND title ~ \"VPN\"', 'text ~ \"troubleshooting\"'.",
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
                "space_key": {"type": "string", "description": "Space key (e.g., ITKB)"},
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
# Helper: extract plain text from Atlassian Document Format (ADF)
# ---------------------------------------------------------------------------
def _adf_to_text(adf: Optional[dict]) -> str:
    """Recursively extract plain text from ADF JSON."""
    if not adf:
        return ""
    if isinstance(adf, str):
        return adf

    text_parts = []

    if adf.get("type") == "text":
        return adf.get("text", "")

    for child in adf.get("content", []):
        child_text = _adf_to_text(child)
        if child_text:
            text_parts.append(child_text)

    node_type = adf.get("type", "")
    separator = "\n" if node_type in ("paragraph", "heading", "listItem", "bulletList", "orderedList", "codeBlock", "blockquote") else " "
    return separator.join(text_parts)


def _html_to_text(html: str) -> str:
    """Strip HTML tags for readable output."""
    clean = re.sub(r"<[^>]+>", " ", html)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


# ---------------------------------------------------------------------------
# Tool implementations — Real API calls
# ---------------------------------------------------------------------------
def execute_tool(name: str, arguments: dict) -> dict:
    try:
        # ── Jira Tools ──────────────────────────────────────────────
        if name == "jira_search_issues":
            jql = arguments.get("jql", "")
            max_results = min(arguments.get("max_results", 10), 50)
            resp = _jira("GET", "/search/jql", params={
                "jql": jql,
                "fields": "summary,status,priority,assignee,issuetype,created,updated",
                "maxResults": max_results,
            })
            if resp.status_code != 200:
                return {"error": f"Jira search failed ({resp.status_code}): {resp.text[:300]}"}

            data = resp.json()
            issues = data.get("issues", [])
            if not issues:
                return {"text": f"No issues found matching: {jql}"}

            lines = [f"Found {len(issues)} issue(s) matching: {jql}\n"]
            for iss in issues:
                f = iss["fields"]
                assignee = f.get("assignee", {})
                assignee_name = assignee.get("displayName", "Unassigned") if assignee else "Unassigned"
                priority = f.get("priority", {})
                priority_name = priority.get("name", "None") if priority else "None"
                status = f.get("status", {}).get("name", "Unknown")
                itype = f.get("issuetype", {}).get("name", "Unknown")
                lines.append(
                    f"[{iss['key']}] {f.get('summary', '')}\n"
                    f"  Status: {status} | Priority: {priority_name} | Type: {itype}\n"
                    f"  Assignee: {assignee_name}"
                )
            return {"text": "\n\n".join(lines)}

        if name == "jira_get_issue":
            key = arguments.get("issue_key", "").upper()
            resp = _jira("GET", f"/issue/{key}", params={
                "fields": "summary,description,status,priority,assignee,reporter,issuetype,labels,comment,created,updated",
            })
            if resp.status_code == 404:
                return {"error": f"Issue {key} not found"}
            if resp.status_code != 200:
                return {"error": f"Failed to get issue ({resp.status_code}): {resp.text[:300]}"}

            f = resp.json()["fields"]
            assignee = f.get("assignee")
            reporter = f.get("reporter")
            description = _adf_to_text(f.get("description")) or "No description"
            labels = ", ".join(f.get("labels", [])) or "None"
            priority = f.get("priority", {})

            lines = [
                f"{'=' * 60}",
                f"{key}: {f.get('summary', '')}",
                f"{'=' * 60}",
                f"Type:      {f.get('issuetype', {}).get('name', 'Unknown')}",
                f"Status:    {f.get('status', {}).get('name', 'Unknown')}",
                f"Priority:  {priority.get('name', 'None') if priority else 'None'}",
                f"Assignee:  {assignee.get('displayName', 'Unassigned') if assignee else 'Unassigned'}",
                f"Reporter:  {reporter.get('displayName', 'Unknown') if reporter else 'Unknown'}",
                f"Labels:    {labels}",
                f"Created:   {f.get('created', '')}",
                f"Updated:   {f.get('updated', '')}",
                f"",
                f"Description:",
                f"  {description}",
            ]

            comments = f.get("comment", {}).get("comments", [])
            if comments:
                lines.append(f"\nComments ({len(comments)}):")
                for c in comments:
                    author = c.get("author", {}).get("displayName", "Unknown")
                    created = c.get("created", "")
                    body = _adf_to_text(c.get("body"))
                    lines.append(f"  [{created}] {author}:")
                    lines.append(f"    {body}")

            return {"text": "\n".join(lines)}

        if name == "jira_create_issue":
            project_key = arguments.get("project_key", "MYS").upper()
            summary = arguments.get("summary", "")
            issue_type = arguments.get("issue_type", "Task")
            priority = arguments.get("priority", "Medium")
            description_text = arguments.get("description", "")
            labels = arguments.get("labels", [])

            # Build ADF description
            desc_adf = None
            if description_text:
                desc_adf = {
                    "type": "doc",
                    "version": 1,
                    "content": [{"type": "paragraph", "content": [{"type": "text", "text": description_text}]}]
                }

            fields = {
                "project": {"key": project_key},
                "summary": summary,
                "issuetype": {"name": issue_type},
                "priority": {"name": priority},
            }
            if desc_adf:
                fields["description"] = desc_adf
            if labels:
                fields["labels"] = labels

            # Resolve assignee by email
            if arguments.get("assignee_email"):
                users_resp = _jira("GET", "/user/search", params={"query": arguments["assignee_email"]})
                if users_resp.status_code == 200:
                    users = users_resp.json()
                    if users:
                        fields["assignee"] = {"accountId": users[0]["accountId"]}

            resp = _jira("POST", "/issue", json={"fields": fields})
            if resp.status_code not in (200, 201):
                return {"error": f"Failed to create issue ({resp.status_code}): {resp.text[:300]}"}

            created = resp.json()
            new_key = created.get("key", "?")
            return {"text": f"✅ Created issue {new_key}: {summary}\n\nURL: {BASE_URL}/browse/{new_key}"}

        if name == "jira_update_issue":
            key = arguments.get("issue_key", "").upper()
            fields = {}
            changes = []

            if arguments.get("summary"):
                fields["summary"] = arguments["summary"]
                changes.append(f"  summary → {arguments['summary']}")
            if arguments.get("description"):
                fields["description"] = {
                    "type": "doc", "version": 1,
                    "content": [{"type": "paragraph", "content": [{"type": "text", "text": arguments["description"]}]}]
                }
                changes.append("  description → (updated)")
            if arguments.get("priority"):
                fields["priority"] = {"name": arguments["priority"]}
                changes.append(f"  priority → {arguments['priority']}")
            if arguments.get("labels") is not None:
                fields["labels"] = arguments["labels"]
                changes.append(f"  labels → {arguments['labels']}")

            if arguments.get("assignee_email"):
                users_resp = _jira("GET", "/user/search", params={"query": arguments["assignee_email"]})
                if users_resp.status_code == 200:
                    users = users_resp.json()
                    if users:
                        fields["assignee"] = {"accountId": users[0]["accountId"]}
                        changes.append(f"  assignee → {users[0].get('displayName', arguments['assignee_email'])}")

            if not fields:
                return {"text": f"No changes specified for {key}."}

            resp = _jira("PUT", f"/issue/{key}", json={"fields": fields})
            if resp.status_code == 404:
                return {"error": f"Issue {key} not found"}
            if resp.status_code not in (200, 204):
                return {"error": f"Failed to update ({resp.status_code}): {resp.text[:300]}"}

            return {"text": f"✅ Updated {key}:\n" + "\n".join(changes)}

        if name == "jira_add_comment":
            key = arguments.get("issue_key", "").upper()
            body_text = arguments.get("body", "")
            comment_adf = {
                "body": {
                    "type": "doc", "version": 1,
                    "content": [{"type": "paragraph", "content": [{"type": "text", "text": body_text}]}]
                }
            }
            resp = _jira("POST", f"/issue/{key}/comment", json=comment_adf)
            if resp.status_code == 404:
                return {"error": f"Issue {key} not found"}
            if resp.status_code not in (200, 201):
                return {"error": f"Failed to add comment ({resp.status_code}): {resp.text[:300]}"}

            return {"text": f"✅ Comment added to {key}."}

        if name == "jira_list_projects":
            resp = _jira("GET", "/project", params={"maxResults": 50})
            if resp.status_code != 200:
                return {"error": f"Failed to list projects ({resp.status_code}): {resp.text[:300]}"}
            projects = resp.json()
            lines = ["Jira Projects:\n"]
            for p in projects:
                lead = p.get("lead", {})
                lead_name = lead.get("displayName", "Unknown") if lead else "Unknown"
                lines.append(f"  [{p['key']}] {p['name']} (Lead: {lead_name})")
            return {"text": "\n".join(lines)}

        if name == "jira_get_transitions":
            key = arguments.get("issue_key", "").upper()
            resp = _jira("GET", f"/issue/{key}/transitions")
            if resp.status_code == 404:
                return {"error": f"Issue {key} not found"}
            if resp.status_code != 200:
                return {"error": f"Failed to get transitions ({resp.status_code}): {resp.text[:300]}"}

            transitions = resp.json().get("transitions", [])
            # Get current status
            issue_resp = _jira("GET", f"/issue/{key}", params={"fields": "status"})
            current = "Unknown"
            if issue_resp.status_code == 200:
                current = issue_resp.json().get("fields", {}).get("status", {}).get("name", "Unknown")

            lines = [f"Current status: {current}", "Available transitions:"]
            for t in transitions:
                lines.append(f"  → {t['name']} (id: {t['id']})")
            return {"text": "\n".join(lines)}

        # ── Confluence Tools ────────────────────────────────────────
        if name == "confluence_search":
            query = arguments.get("query", "")
            max_results = min(arguments.get("max_results", 10), 25)

            # Try CQL search first
            resp = _confluence_v1("GET", "/content/search", params={
                "cql": query,
                "limit": max_results,
                "expand": "version,space",
            })
            # If CQL fails, fall back to text search
            if resp.status_code != 200:
                resp = _confluence_v1("GET", "/content/search", params={
                    "cql": f'text ~ "{query}"',
                    "limit": max_results,
                    "expand": "version,space",
                })
            if resp.status_code != 200:
                return {"error": f"Confluence search failed ({resp.status_code}): {resp.text[:300]}"}

            results = resp.json().get("results", [])
            if not results:
                return {"text": f"No Confluence pages found matching: {query}"}

            lines = [f"Found {len(results)} page(s):\n"]
            for p in results:
                space_key = p.get("space", {}).get("key", "?") if "space" in p else "?"
                version = p.get("version", {}).get("number", "?")
                by = p.get("version", {}).get("by", {}).get("displayName", "Unknown")
                when = p.get("version", {}).get("when", "")
                lines.append(f"  [{space_key}] {p.get('title', '?')} (id: {p['id']}, v{version})")
                lines.append(f"    Last updated: {when} by {by}")
            return {"text": "\n".join(lines)}

        if name == "confluence_get_page":
            page = None
            page_id = arguments.get("page_id")
            title = arguments.get("title")
            space_key = arguments.get("space_key")

            if page_id:
                resp = _confluence_v1("GET", f"/content/{page_id}", params={
                    "expand": "body.storage,version,space",
                })
                if resp.status_code == 200:
                    page = resp.json()
            elif title:
                cql = f'title = "{title}"'
                if space_key:
                    cql = f'space = "{space_key}" AND title = "{title}"'
                resp = _confluence_v1("GET", "/content/search", params={
                    "cql": cql,
                    "limit": 1,
                    "expand": "body.storage,version,space",
                })
                if resp.status_code == 200:
                    results = resp.json().get("results", [])
                    if results:
                        page = results[0]

            if not page:
                return {"error": "Page not found"}

            body_html = page.get("body", {}).get("storage", {}).get("value", "")
            clean_body = _html_to_text(body_html)
            space_key = page.get("space", {}).get("key", "?")
            version = page.get("version", {}).get("number", "?")
            by = page.get("version", {}).get("by", {}).get("displayName", "Unknown")
            when = page.get("version", {}).get("when", "")

            return {
                "text": (
                    f"{'=' * 60}\n"
                    f"{page.get('title', '?')}\n"
                    f"{'=' * 60}\n"
                    f"Space: {space_key} | Version: {version} | ID: {page['id']}\n"
                    f"Author: {by}\n"
                    f"Last Updated: {when}\n"
                    f"\n{clean_body}"
                )
            }

        if name == "confluence_create_page":
            space_key = arguments.get("space_key", "ITKB").upper()
            title = arguments.get("title", "Untitled")
            body = arguments.get("body", "")
            parent_id = arguments.get("parent_page_id")

            payload = {
                "type": "page",
                "title": title,
                "space": {"key": space_key},
                "body": {
                    "storage": {
                        "value": body,
                        "representation": "storage",
                    }
                },
            }
            if parent_id:
                payload["ancestors"] = [{"id": parent_id}]

            resp = _confluence_v1("POST", "/content", json=payload)
            if resp.status_code not in (200, 201):
                return {"error": f"Failed to create page ({resp.status_code}): {resp.text[:300]}"}

            created = resp.json()
            return {
                "text": (
                    f"✅ Created Confluence page:\n"
                    f"  Title: {created.get('title', title)}\n"
                    f"  Space: {space_key}\n"
                    f"  ID: {created['id']}\n"
                    f"  URL: {BASE_URL}/wiki/spaces/{space_key}/pages/{created['id']}"
                )
            }

        if name == "confluence_update_page":
            page_id = arguments.get("page_id", "")
            new_title = arguments.get("title")
            new_body = arguments.get("body")

            # Get current page to get version number and title
            current_resp = _confluence_v1("GET", f"/content/{page_id}", params={
                "expand": "version,space",
            })
            if current_resp.status_code == 404:
                return {"error": f"Page {page_id} not found"}
            if current_resp.status_code != 200:
                return {"error": f"Failed to get page ({current_resp.status_code}): {current_resp.text[:300]}"}

            current = current_resp.json()
            current_version = current.get("version", {}).get("number", 1)
            current_title = current.get("title", "Untitled")
            space_key = current.get("space", {}).get("key", "?")

            payload = {
                "type": "page",
                "title": new_title or current_title,
                "version": {"number": current_version + 1},
                "body": {
                    "storage": {
                        "value": new_body or "",
                        "representation": "storage",
                    }
                },
            }

            resp = _confluence_v1("PUT", f"/content/{page_id}", json=payload)
            if resp.status_code not in (200, 201):
                return {"error": f"Failed to update page ({resp.status_code}): {resp.text[:300]}"}

            changes = []
            if new_title:
                changes.append(f"  title → {new_title}")
            if new_body:
                changes.append("  body → (updated)")

            return {"text": f"✅ Updated page {page_id} (now v{current_version + 1}):\n" + "\n".join(changes)}

        if name == "confluence_list_spaces":
            resp = _confluence_v2("GET", "/spaces", params={"limit": 50})
            if resp.status_code != 200:
                return {"error": f"Failed to list spaces ({resp.status_code}): {resp.text[:300]}"}

            spaces = resp.json().get("results", [])
            lines = ["Confluence Spaces:\n"]
            for s in spaces:
                lines.append(f"  [{s.get('key', '?')}] {s.get('name', '?')} ({s.get('type', '?')})")
            return {"text": "\n".join(lines)}

        return {"error": f"Unknown tool: {name}"}

    except requests.Timeout:
        return {"error": f"Request timed out calling {name}"}
    except requests.ConnectionError as e:
        return {"error": f"Connection error calling {name}: {e}"}
    except Exception as e:
        logger.error("Tool %s failed: %s", name, e, exc_info=True)
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# JSON-RPC 2.0 handler
# ---------------------------------------------------------------------------
def handle_jsonrpc(body: dict) -> Optional[dict]:
    method = body.get("method", "")
    req_id = body.get("id")
    params = body.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "Atlassian MCP Server", "version": "1.0.0"},
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
        raw = self.rfile.read(length)
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return

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

    def do_GET(self):
        """Health check endpoint."""
        if self.path == "/healthz":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, fmt, *args):
        logger.debug(fmt % args)


if __name__ == "__main__":
    PORT = int(os.environ.get("MCP_PORT", "8082"))
    server = HTTPServer(("0.0.0.0", PORT), MCPHandler)
    logger.info("🚀 Atlassian MCP Server (REAL) running on http://0.0.0.0:%d/mcp", PORT)
    logger.info("   Base URL: %s", BASE_URL)
    logger.info("   Email:    %s", EMAIL)
    logger.info("   Token:    %s", "***" + API_TOKEN[-4:] if len(API_TOKEN) > 4 else "(not set)")
    logger.info("   Tools:    %s", ", ".join(t["name"] for t in TOOLS))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
