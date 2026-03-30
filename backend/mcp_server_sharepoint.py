"""
SharePoint + OneDrive MCP server.

Connects to Microsoft Graph API using app-level or delegated auth.
Credentials come from environment variables (injected from Azure Key Vault).

Run locally:
    export SHAREPOINT_TENANT_ID=<tenant-id>
    export SHAREPOINT_CLIENT_ID=<client-id>
    export SHAREPOINT_CLIENT_SECRET=<client-secret>
    export SHAREPOINT_SITE_HOSTNAME=<org>.sharepoint.com
    cd backend && python mcp_server_sharepoint.py

Register in the UI:
    URL: http://localhost:8083/mcp
    Auth: none (auth is handled server-side)

Tools provided (8 total):
  Sites (2):
    - sharepoint_list_sites, sharepoint_get_site
  Pages / Content (3):
    - sharepoint_search, sharepoint_get_page, sharepoint_list_pages
  Files / OneDrive (3):
    - sharepoint_list_files, sharepoint_get_file_content,
      sharepoint_upload_file
"""

import json
import os
import re
import uuid
import logging
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Optional

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-sharepoint")

# ---------------------------------------------------------------------------
# Configuration from environment
# ---------------------------------------------------------------------------
TENANT_ID = os.environ.get("SHAREPOINT_TENANT_ID", "")
CLIENT_ID = os.environ.get("SHAREPOINT_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("SHAREPOINT_CLIENT_SECRET", "")
SITE_HOSTNAME = os.environ.get("SHAREPOINT_SITE_HOSTNAME", "")  # e.g. contoso.sharepoint.com

if not all([TENANT_ID, CLIENT_ID, CLIENT_SECRET]):
    logger.warning("SharePoint credentials not fully set — API calls will fail")

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
TIMEOUT = 30

# ---------------------------------------------------------------------------
# OAuth2 token management (client credentials flow)
# ---------------------------------------------------------------------------
_token_cache: Dict[str, any] = {"access_token": "", "expires_at": 0}


def _get_token() -> str:
    """Get a valid access token, refreshing if expired."""
    now = time.time()
    if _token_cache["access_token"] and _token_cache["expires_at"] > now + 60:
        return _token_cache["access_token"]

    token_url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    resp = requests.post(token_url, data={
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "https://graph.microsoft.com/.default",
    }, timeout=TIMEOUT)

    if resp.status_code != 200:
        logger.error("Token acquisition failed: %s", resp.text[:300])
        raise RuntimeError(f"Failed to acquire token: {resp.status_code}")

    data = resp.json()
    _token_cache["access_token"] = data["access_token"]
    _token_cache["expires_at"] = now + data.get("expires_in", 3600)
    return _token_cache["access_token"]


def _graph(method: str, path: str, **kwargs) -> requests.Response:
    """Make authenticated request to Microsoft Graph API."""
    token = _get_token()
    headers = kwargs.pop("headers", {})
    headers["Authorization"] = f"Bearer {token}"
    url = f"{GRAPH_BASE}{path}"
    return requests.request(method, url, headers=headers, timeout=TIMEOUT, **kwargs)


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------
TOOLS = [
    {
        "name": "sharepoint_list_sites",
        "description": "List SharePoint sites the application has access to. Returns site name, URL, and ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "search": {"type": "string", "description": "Optional search query to filter sites"},
            },
        },
    },
    {
        "name": "sharepoint_get_site",
        "description": "Get details of a specific SharePoint site by hostname and path, or by site ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "site_id": {"type": "string", "description": "Site ID (optional if hostname/path provided)"},
                "site_path": {"type": "string", "description": "Site relative path, e.g. '/sites/Engineering' (optional if site_id provided)"},
            },
        },
    },
    {
        "name": "sharepoint_search",
        "description": "Search across SharePoint content (pages, documents, list items) using keyword query.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query text"},
                "max_results": {"type": "integer", "description": "Max results (default: 10)", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "sharepoint_list_pages",
        "description": "List pages in a SharePoint site.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "site_id": {"type": "string", "description": "Site ID"},
            },
            "required": ["site_id"],
        },
    },
    {
        "name": "sharepoint_get_page",
        "description": "Get a SharePoint page by ID, including its web parts and content.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "site_id": {"type": "string", "description": "Site ID"},
                "page_id": {"type": "string", "description": "Page ID"},
            },
            "required": ["site_id", "page_id"],
        },
    },
    {
        "name": "sharepoint_list_files",
        "description": "List files and folders in a SharePoint document library or OneDrive folder.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "site_id": {"type": "string", "description": "Site ID"},
                "folder_path": {"type": "string", "description": "Folder path relative to document library root (default: root)", "default": "/"},
                "drive_id": {"type": "string", "description": "Drive ID (optional, uses default document library)"},
            },
            "required": ["site_id"],
        },
    },
    {
        "name": "sharepoint_get_file_content",
        "description": "Get the text content of a file from SharePoint/OneDrive. Works best with .txt, .md, .csv, .json files. For Office documents, returns metadata.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "site_id": {"type": "string", "description": "Site ID"},
                "item_id": {"type": "string", "description": "File item ID"},
                "drive_id": {"type": "string", "description": "Drive ID (optional)"},
            },
            "required": ["site_id", "item_id"],
        },
    },
    {
        "name": "sharepoint_upload_file",
        "description": "Upload a small file (< 4MB) to a SharePoint document library.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "site_id": {"type": "string", "description": "Site ID"},
                "folder_path": {"type": "string", "description": "Target folder path (e.g., '/General')"},
                "file_name": {"type": "string", "description": "File name to create"},
                "content": {"type": "string", "description": "File content (text)"},
                "drive_id": {"type": "string", "description": "Drive ID (optional)"},
            },
            "required": ["site_id", "file_name", "content"],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------
def execute_tool(name: str, arguments: dict) -> dict:
    try:
        if name == "sharepoint_list_sites":
            search = arguments.get("search")
            if search:
                resp = _graph("GET", f"/sites?search={search}&$top=25")
            else:
                resp = _graph("GET", "/sites?$top=25")

            if resp.status_code != 200:
                return {"error": f"Failed to list sites ({resp.status_code}): {resp.text[:300]}"}

            sites = resp.json().get("value", [])
            if not sites:
                return {"text": "No SharePoint sites found."}

            lines = [f"Found {len(sites)} site(s):\n"]
            for s in sites:
                lines.append(
                    f"  [{s.get('displayName', '?')}]\n"
                    f"    URL: {s.get('webUrl', '?')}\n"
                    f"    ID: {s.get('id', '?')}"
                )
            return {"text": "\n".join(lines)}

        if name == "sharepoint_get_site":
            site_id = arguments.get("site_id")
            site_path = arguments.get("site_path", "")

            if site_id:
                resp = _graph("GET", f"/sites/{site_id}")
            elif site_path and SITE_HOSTNAME:
                resp = _graph("GET", f"/sites/{SITE_HOSTNAME}:{site_path}")
            else:
                return {"error": "Provide site_id or site_path (with SHAREPOINT_SITE_HOSTNAME configured)"}

            if resp.status_code == 404:
                return {"error": "Site not found"}
            if resp.status_code != 200:
                return {"error": f"Failed to get site ({resp.status_code}): {resp.text[:300]}"}

            s = resp.json()
            return {
                "text": (
                    f"{'=' * 60}\n"
                    f"{s.get('displayName', '?')}\n"
                    f"{'=' * 60}\n"
                    f"URL:         {s.get('webUrl', '?')}\n"
                    f"ID:          {s.get('id', '?')}\n"
                    f"Description: {s.get('description', 'N/A')}\n"
                    f"Created:     {s.get('createdDateTime', '?')}\n"
                    f"Modified:    {s.get('lastModifiedDateTime', '?')}"
                )
            }

        if name == "sharepoint_search":
            query = arguments.get("query", "")
            max_results = min(arguments.get("max_results", 10), 25)

            resp = _graph("POST", "/search/query", json={
                "requests": [{
                    "entityTypes": ["driveItem", "listItem", "site"],
                    "query": {"queryString": query},
                    "from": 0,
                    "size": max_results,
                }]
            })

            if resp.status_code != 200:
                return {"error": f"Search failed ({resp.status_code}): {resp.text[:300]}"}

            hits = []
            for result_set in resp.json().get("value", []):
                for hit_container in result_set.get("hitsContainers", []):
                    for hit in hit_container.get("hits", []):
                        resource = hit.get("resource", {})
                        hits.append({
                            "name": resource.get("name", resource.get("displayName", "?")),
                            "url": resource.get("webUrl", "?"),
                            "type": hit.get("resource", {}).get("@odata.type", "?"),
                            "summary": hit.get("summary", ""),
                        })

            if not hits:
                return {"text": f"No results found for: {query}"}

            lines = [f"Found {len(hits)} result(s) for: {query}\n"]
            for h in hits:
                lines.append(f"  {h['name']}\n    URL: {h['url']}\n    Type: {h['type']}")
                if h["summary"]:
                    clean = re.sub(r"<[^>]+>", "", h["summary"]).strip()
                    lines.append(f"    Summary: {clean[:200]}")
            return {"text": "\n".join(lines)}

        if name == "sharepoint_list_pages":
            site_id = arguments.get("site_id", "")
            resp = _graph("GET", f"/sites/{site_id}/pages?$top=25")

            if resp.status_code != 200:
                return {"error": f"Failed to list pages ({resp.status_code}): {resp.text[:300]}"}

            pages = resp.json().get("value", [])
            if not pages:
                return {"text": "No pages found in this site."}

            lines = [f"Found {len(pages)} page(s):\n"]
            for p in pages:
                lines.append(
                    f"  {p.get('title', '?')} (id: {p.get('id', '?')})\n"
                    f"    URL: {p.get('webUrl', '?')}\n"
                    f"    Modified: {p.get('lastModifiedDateTime', '?')}"
                )
            return {"text": "\n".join(lines)}

        if name == "sharepoint_get_page":
            site_id = arguments.get("site_id", "")
            page_id = arguments.get("page_id", "")
            resp = _graph("GET", f"/sites/{site_id}/pages/{page_id}?$expand=canvasLayout")

            if resp.status_code == 404:
                return {"error": "Page not found"}
            if resp.status_code != 200:
                return {"error": f"Failed to get page ({resp.status_code}): {resp.text[:300]}"}

            p = resp.json()
            # Extract text from web parts
            content_parts = []
            layout = p.get("canvasLayout", {})
            for section in layout.get("horizontalSections", []):
                for column in section.get("columns", []):
                    for wp in column.get("webparts", []):
                        inner = wp.get("innerHtml", "")
                        if inner:
                            clean = re.sub(r"<[^>]+>", " ", inner)
                            clean = re.sub(r"\s+", " ", clean).strip()
                            if clean:
                                content_parts.append(clean)

            body = "\n\n".join(content_parts) if content_parts else "(No extractable content)"

            return {
                "text": (
                    f"{'=' * 60}\n"
                    f"{p.get('title', '?')}\n"
                    f"{'=' * 60}\n"
                    f"ID:       {p.get('id', '?')}\n"
                    f"URL:      {p.get('webUrl', '?')}\n"
                    f"Modified: {p.get('lastModifiedDateTime', '?')}\n"
                    f"\n{body}"
                )
            }

        if name == "sharepoint_list_files":
            site_id = arguments.get("site_id", "")
            folder_path = arguments.get("folder_path", "/")
            drive_id = arguments.get("drive_id")

            if drive_id:
                base = f"/drives/{drive_id}"
            else:
                base = f"/sites/{site_id}/drive"

            if folder_path and folder_path != "/":
                path = folder_path.strip("/")
                resp = _graph("GET", f"{base}/root:/{path}:/children?$top=50")
            else:
                resp = _graph("GET", f"{base}/root/children?$top=50")

            if resp.status_code != 200:
                return {"error": f"Failed to list files ({resp.status_code}): {resp.text[:300]}"}

            items = resp.json().get("value", [])
            if not items:
                return {"text": "No files found in this location."}

            lines = [f"Found {len(items)} item(s):\n"]
            for item in items:
                is_folder = "folder" in item
                size = item.get("size", 0)
                size_str = f"{size / 1024:.1f} KB" if size < 1048576 else f"{size / 1048576:.1f} MB"
                icon = "📁" if is_folder else "📄"
                lines.append(
                    f"  {icon} {item.get('name', '?')}\n"
                    f"    ID: {item.get('id', '?')} | Size: {size_str}\n"
                    f"    Modified: {item.get('lastModifiedDateTime', '?')}"
                )
            return {"text": "\n".join(lines)}

        if name == "sharepoint_get_file_content":
            site_id = arguments.get("site_id", "")
            item_id = arguments.get("item_id", "")
            drive_id = arguments.get("drive_id")

            if drive_id:
                base = f"/drives/{drive_id}"
            else:
                base = f"/sites/{site_id}/drive"

            # Get file metadata first
            meta_resp = _graph("GET", f"{base}/items/{item_id}")
            if meta_resp.status_code != 200:
                return {"error": f"File not found ({meta_resp.status_code})"}

            meta = meta_resp.json()
            name_str = meta.get("name", "?")
            size = meta.get("size", 0)
            mime = meta.get("file", {}).get("mimeType", "unknown")

            # For text-like files, download content
            text_types = ["text/", "application/json", "application/xml", "application/csv"]
            is_text = any(mime.startswith(t) for t in text_types) or name_str.endswith((".md", ".txt", ".csv", ".json", ".xml", ".yaml", ".yml"))

            if is_text and size < 1048576:  # < 1MB
                content_resp = _graph("GET", f"{base}/items/{item_id}/content")
                if content_resp.status_code == 200:
                    content = content_resp.text[:10000]  # Cap at 10K chars
                    return {
                        "text": (
                            f"File: {name_str} ({mime}, {size} bytes)\n"
                            f"{'=' * 60}\n"
                            f"{content}"
                        )
                    }

            return {
                "text": (
                    f"File: {name_str}\n"
                    f"Type: {mime}\n"
                    f"Size: {size} bytes\n"
                    f"URL: {meta.get('webUrl', '?')}\n"
                    f"(Binary/large file — content not displayed)"
                )
            }

        if name == "sharepoint_upload_file":
            site_id = arguments.get("site_id", "")
            folder_path = arguments.get("folder_path", "/General").strip("/")
            file_name = arguments.get("file_name", "")
            content = arguments.get("content", "")
            drive_id = arguments.get("drive_id")

            if drive_id:
                base = f"/drives/{drive_id}"
            else:
                base = f"/sites/{site_id}/drive"

            upload_path = f"{folder_path}/{file_name}" if folder_path else file_name
            resp = _graph("PUT", f"{base}/root:/{upload_path}:/content",
                          data=content.encode("utf-8"),
                          headers={"Content-Type": "text/plain"})

            if resp.status_code not in (200, 201):
                return {"error": f"Upload failed ({resp.status_code}): {resp.text[:300]}"}

            item = resp.json()
            return {
                "text": (
                    f"✅ Uploaded file:\n"
                    f"  Name: {item.get('name', file_name)}\n"
                    f"  ID: {item.get('id', '?')}\n"
                    f"  URL: {item.get('webUrl', '?')}\n"
                    f"  Size: {item.get('size', 0)} bytes"
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
                "serverInfo": {"name": "SharePoint MCP Server", "version": "1.0.0"},
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
    PORT = int(os.environ.get("MCP_PORT", "8083"))
    server = HTTPServer(("0.0.0.0", PORT), MCPHandler)
    logger.info("🚀 SharePoint MCP Server running on http://0.0.0.0:%d/mcp", PORT)
    logger.info("   Tenant ID: %s", TENANT_ID[:8] + "..." if TENANT_ID else "(not set)")
    logger.info("   Site Host: %s", SITE_HOSTNAME or "(not set)")
    logger.info("   Tools:     %s", ", ".join(t["name"] for t in TOOLS))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
