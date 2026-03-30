"""
GitHub MCP server.

Connects to GitHub REST and GraphQL APIs using a Personal Access Token
or GitHub App credentials.

Run locally:
    export GITHUB_TOKEN=ghp_xxx
    cd backend && python mcp_server_github.py

Register in the UI:
    URL: http://localhost:8084/mcp
    Auth: none (auth is handled server-side)

Tools provided (10 total):
  Repositories (3):
    - github_list_repos, github_get_repo, github_search_code
  Issues (3):
    - github_list_issues, github_get_issue, github_create_issue
  Pull Requests (3):
    - github_list_pull_requests, github_get_pull_request,
      github_create_pull_request
  General (1):
    - github_search_repos
"""

import json
import os
import re
import uuid
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-github")

# ---------------------------------------------------------------------------
# Configuration from environment
# ---------------------------------------------------------------------------
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_API_BASE = os.environ.get("GITHUB_API_BASE", "https://api.github.com")
DEFAULT_ORG = os.environ.get("GITHUB_DEFAULT_ORG", "")

if not GITHUB_TOKEN:
    logger.warning("GITHUB_TOKEN not set — API calls will fail")

TIMEOUT = 30


def _gh(method: str, path: str, **kwargs) -> requests.Response:
    """Make authenticated request to GitHub REST API."""
    headers = kwargs.pop("headers", {})
    headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    headers["Accept"] = "application/vnd.github+json"
    headers["X-GitHub-Api-Version"] = "2022-11-28"
    url = f"{GITHUB_API_BASE}{path}"
    return requests.request(method, url, headers=headers, timeout=TIMEOUT, **kwargs)


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------
TOOLS = [
    {
        "name": "github_list_repos",
        "description": "List repositories for an organization or the authenticated user.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "org": {"type": "string", "description": "Organization name (optional, defaults to authenticated user's repos)"},
                "sort": {"type": "string", "description": "Sort by: created, updated, pushed, full_name (default: updated)", "default": "updated"},
                "max_results": {"type": "integer", "description": "Max results (default: 20)", "default": 20},
            },
        },
    },
    {
        "name": "github_get_repo",
        "description": "Get detailed information about a GitHub repository.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Repository owner (user or org)"},
                "repo": {"type": "string", "description": "Repository name"},
            },
            "required": ["owner", "repo"],
        },
    },
    {
        "name": "github_search_repos",
        "description": "Search GitHub repositories by keyword, language, or other criteria.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query (supports GitHub search syntax, e.g. 'fastapi language:python')"},
                "max_results": {"type": "integer", "description": "Max results (default: 10)", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "github_search_code",
        "description": "Search code across repositories. Requires at least one qualifier (repo, org, user, or language).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query with qualifiers (e.g. 'TODO repo:owner/repo language:python')"},
                "max_results": {"type": "integer", "description": "Max results (default: 10)", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "github_list_issues",
        "description": "List issues in a repository. Supports filtering by state, labels, assignee.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Repository owner"},
                "repo": {"type": "string", "description": "Repository name"},
                "state": {"type": "string", "description": "Filter by state: open, closed, all (default: open)", "default": "open"},
                "labels": {"type": "string", "description": "Comma-separated label names to filter by"},
                "assignee": {"type": "string", "description": "Filter by assignee username"},
                "max_results": {"type": "integer", "description": "Max results (default: 20)", "default": 20},
            },
            "required": ["owner", "repo"],
        },
    },
    {
        "name": "github_get_issue",
        "description": "Get full details of a GitHub issue including body, comments, labels, and assignees.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Repository owner"},
                "repo": {"type": "string", "description": "Repository name"},
                "issue_number": {"type": "integer", "description": "Issue number"},
            },
            "required": ["owner", "repo", "issue_number"],
        },
    },
    {
        "name": "github_create_issue",
        "description": "Create a new issue in a GitHub repository.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Repository owner"},
                "repo": {"type": "string", "description": "Repository name"},
                "title": {"type": "string", "description": "Issue title"},
                "body": {"type": "string", "description": "Issue body (Markdown)"},
                "labels": {"type": "array", "items": {"type": "string"}, "description": "Labels to apply"},
                "assignees": {"type": "array", "items": {"type": "string"}, "description": "GitHub usernames to assign"},
            },
            "required": ["owner", "repo", "title"],
        },
    },
    {
        "name": "github_list_pull_requests",
        "description": "List pull requests in a repository.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Repository owner"},
                "repo": {"type": "string", "description": "Repository name"},
                "state": {"type": "string", "description": "Filter by state: open, closed, all (default: open)", "default": "open"},
                "sort": {"type": "string", "description": "Sort by: created, updated, popularity (default: updated)", "default": "updated"},
                "max_results": {"type": "integer", "description": "Max results (default: 20)", "default": 20},
            },
            "required": ["owner", "repo"],
        },
    },
    {
        "name": "github_get_pull_request",
        "description": "Get full details of a pull request including diff stats, reviews, and comments.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Repository owner"},
                "repo": {"type": "string", "description": "Repository name"},
                "pr_number": {"type": "integer", "description": "Pull request number"},
            },
            "required": ["owner", "repo", "pr_number"],
        },
    },
    {
        "name": "github_create_pull_request",
        "description": "Create a new pull request.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Repository owner"},
                "repo": {"type": "string", "description": "Repository name"},
                "title": {"type": "string", "description": "PR title"},
                "body": {"type": "string", "description": "PR description (Markdown)"},
                "head": {"type": "string", "description": "Branch containing changes"},
                "base": {"type": "string", "description": "Branch to merge into (default: main)", "default": "main"},
            },
            "required": ["owner", "repo", "title", "head"],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------
def execute_tool(name: str, arguments: dict) -> dict:
    try:
        if name == "github_list_repos":
            org = arguments.get("org", DEFAULT_ORG)
            sort = arguments.get("sort", "updated")
            per_page = min(arguments.get("max_results", 20), 100)

            if org:
                resp = _gh("GET", f"/orgs/{org}/repos", params={"sort": sort, "per_page": per_page})
            else:
                resp = _gh("GET", "/user/repos", params={"sort": sort, "per_page": per_page})

            if resp.status_code != 200:
                return {"error": f"Failed to list repos ({resp.status_code}): {resp.text[:300]}"}

            repos = resp.json()
            lines = [f"Found {len(repos)} repository(ies):\n"]
            for r in repos:
                lang = r.get("language", "N/A")
                stars = r.get("stargazers_count", 0)
                visibility = "🔒" if r.get("private") else "🌐"
                lines.append(
                    f"  {visibility} {r['full_name']}\n"
                    f"    {r.get('description', 'No description') or 'No description'}\n"
                    f"    Language: {lang} | Stars: {stars} | Updated: {r.get('updated_at', '?')}"
                )
            return {"text": "\n".join(lines)}

        if name == "github_get_repo":
            owner = arguments["owner"]
            repo = arguments["repo"]
            resp = _gh("GET", f"/repos/{owner}/{repo}")

            if resp.status_code == 404:
                return {"error": f"Repository {owner}/{repo} not found"}
            if resp.status_code != 200:
                return {"error": f"Failed ({resp.status_code}): {resp.text[:300]}"}

            r = resp.json()
            return {
                "text": (
                    f"{'=' * 60}\n"
                    f"{r['full_name']}\n"
                    f"{'=' * 60}\n"
                    f"Description:   {r.get('description', 'N/A')}\n"
                    f"URL:           {r.get('html_url', '?')}\n"
                    f"Language:      {r.get('language', 'N/A')}\n"
                    f"Stars:         {r.get('stargazers_count', 0)}\n"
                    f"Forks:         {r.get('forks_count', 0)}\n"
                    f"Open Issues:   {r.get('open_issues_count', 0)}\n"
                    f"Default Branch:{r.get('default_branch', 'main')}\n"
                    f"Visibility:    {'Private' if r.get('private') else 'Public'}\n"
                    f"Created:       {r.get('created_at', '?')}\n"
                    f"Updated:       {r.get('updated_at', '?')}\n"
                    f"Topics:        {', '.join(r.get('topics', [])) or 'None'}"
                )
            }

        if name == "github_search_repos":
            query = arguments["query"]
            per_page = min(arguments.get("max_results", 10), 30)
            resp = _gh("GET", "/search/repositories", params={"q": query, "per_page": per_page})

            if resp.status_code != 200:
                return {"error": f"Search failed ({resp.status_code}): {resp.text[:300]}"}

            items = resp.json().get("items", [])
            if not items:
                return {"text": f"No repositories found for: {query}"}

            lines = [f"Found {len(items)} repo(s) for: {query}\n"]
            for r in items:
                lines.append(
                    f"  {r['full_name']} ⭐ {r.get('stargazers_count', 0)}\n"
                    f"    {r.get('description', 'No description') or 'No description'}\n"
                    f"    Language: {r.get('language', 'N/A')} | URL: {r.get('html_url', '?')}"
                )
            return {"text": "\n".join(lines)}

        if name == "github_search_code":
            query = arguments["query"]
            per_page = min(arguments.get("max_results", 10), 30)
            resp = _gh("GET", "/search/code", params={"q": query, "per_page": per_page})

            if resp.status_code != 200:
                return {"error": f"Code search failed ({resp.status_code}): {resp.text[:300]}"}

            items = resp.json().get("items", [])
            if not items:
                return {"text": f"No code found for: {query}"}

            lines = [f"Found {len(items)} result(s):\n"]
            for item in items:
                repo = item.get("repository", {}).get("full_name", "?")
                lines.append(
                    f"  {repo}/{item.get('path', '?')}\n"
                    f"    URL: {item.get('html_url', '?')}"
                )
            return {"text": "\n".join(lines)}

        if name == "github_list_issues":
            owner = arguments["owner"]
            repo = arguments["repo"]
            params = {
                "state": arguments.get("state", "open"),
                "per_page": min(arguments.get("max_results", 20), 100),
            }
            if arguments.get("labels"):
                params["labels"] = arguments["labels"]
            if arguments.get("assignee"):
                params["assignee"] = arguments["assignee"]

            resp = _gh("GET", f"/repos/{owner}/{repo}/issues", params=params)

            if resp.status_code != 200:
                return {"error": f"Failed to list issues ({resp.status_code}): {resp.text[:300]}"}

            issues = [i for i in resp.json() if "pull_request" not in i]  # Exclude PRs
            if not issues:
                return {"text": f"No issues found in {owner}/{repo} (state: {params['state']})"}

            lines = [f"Found {len(issues)} issue(s) in {owner}/{repo}:\n"]
            for i in issues:
                labels = ", ".join(l["name"] for l in i.get("labels", []))
                assignee = i.get("assignee", {})
                assignee_name = assignee.get("login", "Unassigned") if assignee else "Unassigned"
                lines.append(
                    f"  #{i['number']} {i.get('title', '?')}\n"
                    f"    State: {i.get('state', '?')} | Labels: {labels or 'None'} | Assignee: {assignee_name}\n"
                    f"    Created: {i.get('created_at', '?')}"
                )
            return {"text": "\n".join(lines)}

        if name == "github_get_issue":
            owner = arguments["owner"]
            repo = arguments["repo"]
            number = arguments["issue_number"]
            resp = _gh("GET", f"/repos/{owner}/{repo}/issues/{number}")

            if resp.status_code == 404:
                return {"error": f"Issue #{number} not found in {owner}/{repo}"}
            if resp.status_code != 200:
                return {"error": f"Failed ({resp.status_code}): {resp.text[:300]}"}

            i = resp.json()
            labels = ", ".join(l["name"] for l in i.get("labels", []))
            assignees = ", ".join(a["login"] for a in i.get("assignees", []))
            body = i.get("body", "No description") or "No description"

            lines = [
                f"{'=' * 60}",
                f"#{i['number']}: {i.get('title', '?')}",
                f"{'=' * 60}",
                f"State:     {i.get('state', '?')}",
                f"Author:    {i.get('user', {}).get('login', '?')}",
                f"Assignees: {assignees or 'None'}",
                f"Labels:    {labels or 'None'}",
                f"Created:   {i.get('created_at', '?')}",
                f"Updated:   {i.get('updated_at', '?')}",
                f"Comments:  {i.get('comments', 0)}",
                f"URL:       {i.get('html_url', '?')}",
                f"",
                f"Body:",
                body[:3000],
            ]

            # Fetch comments
            if i.get("comments", 0) > 0:
                comments_resp = _gh("GET", f"/repos/{owner}/{repo}/issues/{number}/comments", params={"per_page": 10})
                if comments_resp.status_code == 200:
                    comments = comments_resp.json()
                    lines.append(f"\n--- Comments ({len(comments)}) ---")
                    for c in comments:
                        lines.append(f"\n  [{c.get('created_at', '?')}] {c.get('user', {}).get('login', '?')}:")
                        lines.append(f"  {(c.get('body', '') or '')[:500]}")

            return {"text": "\n".join(lines)}

        if name == "github_create_issue":
            owner = arguments["owner"]
            repo = arguments["repo"]
            payload = {"title": arguments["title"]}
            if arguments.get("body"):
                payload["body"] = arguments["body"]
            if arguments.get("labels"):
                payload["labels"] = arguments["labels"]
            if arguments.get("assignees"):
                payload["assignees"] = arguments["assignees"]

            resp = _gh("POST", f"/repos/{owner}/{repo}/issues", json=payload)

            if resp.status_code not in (200, 201):
                return {"error": f"Failed to create issue ({resp.status_code}): {resp.text[:300]}"}

            created = resp.json()
            return {
                "text": (
                    f"✅ Created issue #{created['number']}: {created.get('title', '')}\n"
                    f"URL: {created.get('html_url', '?')}"
                )
            }

        if name == "github_list_pull_requests":
            owner = arguments["owner"]
            repo = arguments["repo"]
            params = {
                "state": arguments.get("state", "open"),
                "sort": arguments.get("sort", "updated"),
                "per_page": min(arguments.get("max_results", 20), 100),
            }

            resp = _gh("GET", f"/repos/{owner}/{repo}/pulls", params=params)

            if resp.status_code != 200:
                return {"error": f"Failed to list PRs ({resp.status_code}): {resp.text[:300]}"}

            prs = resp.json()
            if not prs:
                return {"text": f"No pull requests found in {owner}/{repo} (state: {params['state']})"}

            lines = [f"Found {len(prs)} PR(s) in {owner}/{repo}:\n"]
            for pr in prs:
                lines.append(
                    f"  #{pr['number']} {pr.get('title', '?')}\n"
                    f"    State: {pr.get('state', '?')} | Author: {pr.get('user', {}).get('login', '?')}\n"
                    f"    {pr.get('head', {}).get('ref', '?')} → {pr.get('base', {}).get('ref', '?')}\n"
                    f"    Created: {pr.get('created_at', '?')}"
                )
            return {"text": "\n".join(lines)}

        if name == "github_get_pull_request":
            owner = arguments["owner"]
            repo = arguments["repo"]
            number = arguments["pr_number"]
            resp = _gh("GET", f"/repos/{owner}/{repo}/pulls/{number}")

            if resp.status_code == 404:
                return {"error": f"PR #{number} not found in {owner}/{repo}"}
            if resp.status_code != 200:
                return {"error": f"Failed ({resp.status_code}): {resp.text[:300]}"}

            pr = resp.json()
            labels = ", ".join(l["name"] for l in pr.get("labels", []))
            reviewers = ", ".join(r["login"] for r in pr.get("requested_reviewers", []))
            body = pr.get("body", "No description") or "No description"

            lines = [
                f"{'=' * 60}",
                f"PR #{pr['number']}: {pr.get('title', '?')}",
                f"{'=' * 60}",
                f"State:      {pr.get('state', '?')} {'(MERGED)' if pr.get('merged') else ''}",
                f"Author:     {pr.get('user', {}).get('login', '?')}",
                f"Branch:     {pr.get('head', {}).get('ref', '?')} → {pr.get('base', {}).get('ref', '?')}",
                f"Labels:     {labels or 'None'}",
                f"Reviewers:  {reviewers or 'None'}",
                f"Mergeable:  {pr.get('mergeable', '?')}",
                f"Additions:  +{pr.get('additions', 0)}",
                f"Deletions:  -{pr.get('deletions', 0)}",
                f"Files:      {pr.get('changed_files', 0)}",
                f"Commits:    {pr.get('commits', 0)}",
                f"Created:    {pr.get('created_at', '?')}",
                f"Updated:    {pr.get('updated_at', '?')}",
                f"URL:        {pr.get('html_url', '?')}",
                f"",
                f"Description:",
                body[:3000],
            ]
            return {"text": "\n".join(lines)}

        if name == "github_create_pull_request":
            owner = arguments["owner"]
            repo = arguments["repo"]
            payload = {
                "title": arguments["title"],
                "head": arguments["head"],
                "base": arguments.get("base", "main"),
            }
            if arguments.get("body"):
                payload["body"] = arguments["body"]

            resp = _gh("POST", f"/repos/{owner}/{repo}/pulls", json=payload)

            if resp.status_code not in (200, 201):
                return {"error": f"Failed to create PR ({resp.status_code}): {resp.text[:300]}"}

            created = resp.json()
            return {
                "text": (
                    f"✅ Created PR #{created['number']}: {created.get('title', '')}\n"
                    f"Branch: {created.get('head', {}).get('ref', '?')} → {created.get('base', {}).get('ref', '?')}\n"
                    f"URL: {created.get('html_url', '?')}"
                )
            }

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
                "serverInfo": {"name": "GitHub MCP Server", "version": "1.0.0"},
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
        tool_args = params.get("arguments", {})
        logger.info("Executing tool: %s with args: %s", tool_name, json.dumps(tool_args)[:200])

        result = execute_tool(tool_name, tool_args)

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
    PORT = int(os.environ.get("MCP_PORT", "8084"))
    server = HTTPServer(("0.0.0.0", PORT), MCPHandler)
    logger.info("🚀 GitHub MCP Server running on http://0.0.0.0:%d/mcp", PORT)
    logger.info("   Token:    %s", "***" + GITHUB_TOKEN[-4:] if len(GITHUB_TOKEN) > 4 else "(not set)")
    logger.info("   Org:      %s", DEFAULT_ORG or "(none)")
    logger.info("   Tools:    %s", ", ".join(t["name"] for t in TOOLS))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
