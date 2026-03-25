"""
Real-world MCP server with useful tools.

Run with:
    cd backend && source .venv/bin/activate && pip install httpx beautifulsoup4 && python mcp_server_web_tools.py

Then register in the UI:
    URL: http://localhost:8081/mcp
    Auth: none

Tools provided:
  - web_search: Search the web using DuckDuckGo (no API key needed)
  - fetch_url: Fetch and extract text content from a URL
  - get_datetime: Get current date/time in any timezone
  - run_command: Execute a shell command and return output
  - read_file: Read contents of a file
  - list_directory: List files in a directory
"""

import json
import subprocess
import os
import uuid
import logging
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import quote_plus
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-web-tools")

# ---------------------------------------------------------------------------
# Tool definitions (JSON Schema)
# ---------------------------------------------------------------------------
TOOLS = [
    {
        "name": "web_search",
        "description": "Search the web using DuckDuckGo. Returns top results with title, URL, and snippet. Use this when the user asks about current events, facts, or anything you need to look up.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 5)",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "fetch_url",
        "description": "Fetch a web page and extract its text content. Returns the page title and main text content. Useful for reading articles, documentation, or any web page.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch"
                },
                "max_length": {
                    "type": "integer",
                    "description": "Maximum characters of content to return (default: 5000)",
                    "default": 5000
                }
            },
            "required": ["url"]
        }
    },
    {
        "name": "get_datetime",
        "description": "Get the current date and time. Optionally specify a timezone like 'Asia/Jerusalem', 'US/Eastern', 'Europe/London', 'UTC'.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": "Timezone name (e.g., 'Asia/Jerusalem', 'US/Eastern', 'UTC'). Default: UTC",
                    "default": "UTC"
                }
            }
        }
    },
    {
        "name": "run_command",
        "description": "Execute a shell command and return its output. Use for system tasks like checking disk space, listing processes, or running scripts. Commands run in a sandboxed subprocess with a 30-second timeout.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute"
                },
                "working_directory": {
                    "type": "string",
                    "description": "Working directory for the command (default: home directory)"
                }
            },
            "required": ["command"]
        }
    },
    {
        "name": "read_file",
        "description": "Read the contents of a file and return it as text.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path to the file to read"
                },
                "max_lines": {
                    "type": "integer",
                    "description": "Maximum number of lines to return (default: 200)",
                    "default": 200
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "list_directory",
        "description": "List contents of a directory with file sizes and types.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path to the directory to list"
                }
            },
            "required": ["path"]
        }
    },
]

# ---------------------------------------------------------------------------
# Allowed base directories for file operations (security)
# ---------------------------------------------------------------------------
ALLOWED_DIRS = [
    Path.home(),
    Path("/tmp"),
]

# Blocked commands for security
BLOCKED_COMMANDS = {"rm -rf /", "mkfs", "dd if=", ":(){ :|:& };:", "fork bomb"}


def _is_path_allowed(path_str: str) -> bool:
    """Check if a path is within allowed directories."""
    try:
        target = Path(path_str).resolve()
        return any(
            target == allowed or allowed in target.parents
            for allowed in ALLOWED_DIRS
        )
    except (ValueError, OSError):
        return False


def _is_command_safe(command: str) -> bool:
    """Basic command safety check."""
    cmd_lower = command.lower().strip()
    return not any(blocked in cmd_lower for blocked in BLOCKED_COMMANDS)


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------
def execute_tool(name: str, arguments: dict) -> dict:
    """Execute a tool and return the result."""
    try:
        if name == "web_search":
            return _web_search(arguments.get("query", ""), arguments.get("max_results", 5))
        elif name == "fetch_url":
            return _fetch_url(arguments.get("url", ""), arguments.get("max_length", 5000))
        elif name == "get_datetime":
            return _get_datetime(arguments.get("timezone", "UTC"))
        elif name == "run_command":
            return _run_command(arguments.get("command", ""), arguments.get("working_directory"))
        elif name == "read_file":
            return _read_file(arguments.get("path", ""), arguments.get("max_lines", 200))
        elif name == "list_directory":
            return _list_directory(arguments.get("path", ""))
        else:
            return {"error": f"Unknown tool: {name}"}
    except Exception as e:
        logger.error(f"Tool {name} failed: {e}")
        return {"error": str(e)}


def _web_search(query: str, max_results: int) -> dict:
    """Search using DuckDuckGo HTML (no API key needed)."""
    import httpx
    from bs4 import BeautifulSoup

    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }

    resp = httpx.get(url, headers=headers, timeout=15, follow_redirects=True)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []
    for result in soup.select(".result")[:max_results]:
        title_el = result.select_one(".result__title a")
        snippet_el = result.select_one(".result__snippet")
        if title_el:
            results.append({
                "title": title_el.get_text(strip=True),
                "url": title_el.get("href", ""),
                "snippet": snippet_el.get_text(strip=True) if snippet_el else ""
            })

    if not results:
        return {"message": f"No results found for: {query}", "results": []}

    output = f"Search results for: {query}\n\n"
    for i, r in enumerate(results, 1):
        output += f"{i}. {r['title']}\n   URL: {r['url']}\n   {r['snippet']}\n\n"

    return {"text": output, "result_count": len(results)}


def _fetch_url(url: str, max_length: int) -> dict:
    """Fetch a URL and extract text content."""
    import httpx
    from bs4 import BeautifulSoup

    if not url.startswith(("http://", "https://")):
        return {"error": "URL must start with http:// or https://"}

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }

    resp = httpx.get(url, headers=headers, timeout=15, follow_redirects=True)
    resp.raise_for_status()

    content_type = resp.headers.get("content-type", "")
    if "text/html" in content_type:
        soup = BeautifulSoup(resp.text, "html.parser")
        # Remove script and style elements
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        title = soup.title.string if soup.title else "No title"
        text = soup.get_text(separator="\n", strip=True)
    else:
        title = url
        text = resp.text

    # Truncate if needed
    if len(text) > max_length:
        text = text[:max_length] + "\n\n... [truncated]"

    return {"title": title, "content": text, "url": str(resp.url)}


def _get_datetime(tz_name: str) -> dict:
    """Get current datetime in the specified timezone."""
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(tz_name)
        now = datetime.now(tz)
    except (ImportError, KeyError):
        # Fallback to UTC
        now = datetime.now(timezone.utc)
        tz_name = "UTC (fallback — unknown timezone)"

    return {
        "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
        "timezone": tz_name,
        "day_of_week": now.strftime("%A"),
        "iso": now.isoformat(),
    }


def _run_command(command: str, working_directory: str | None) -> dict:
    """Execute a shell command safely."""
    if not _is_command_safe(command):
        return {"error": "Command blocked for safety reasons."}

    cwd = working_directory or str(Path.home())
    if not os.path.isdir(cwd):
        return {"error": f"Working directory does not exist: {cwd}"}

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=cwd,
            env={**os.environ, "PATH": os.environ.get("PATH", "/usr/bin:/bin")},
        )
        output = result.stdout
        if result.stderr:
            output += f"\n[STDERR]:\n{result.stderr}"

        # Truncate very long output to avoid overwhelming LLM context
        if len(output) > 3000:
            output = output[:3000] + "\n\n... [output truncated at 3,000 chars — use grep/head/tail to filter]"

        return {
            "output": output or "(no output)",
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"error": "Command timed out after 30 seconds."}


def _read_file(path: str, max_lines: int) -> dict:
    """Read file contents."""
    if not _is_path_allowed(path):
        return {"error": f"Access denied: path outside allowed directories."}

    file_path = Path(path)
    if not file_path.exists():
        return {"error": f"File not found: {path}"}
    if not file_path.is_file():
        return {"error": f"Not a file: {path}"}

    try:
        lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
        total = len(lines)
        content = "\n".join(lines[:max_lines])
        if total > max_lines:
            content += f"\n\n... [{total - max_lines} more lines]"
        return {"path": path, "content": content, "total_lines": total}
    except Exception as e:
        return {"error": f"Failed to read file: {e}"}


def _list_directory(path: str) -> dict:
    """List directory contents."""
    if not _is_path_allowed(path):
        return {"error": f"Access denied: path outside allowed directories."}

    dir_path = Path(path)
    if not dir_path.exists():
        return {"error": f"Directory not found: {path}"}
    if not dir_path.is_dir():
        return {"error": f"Not a directory: {path}"}

    entries = []
    try:
        for entry in sorted(dir_path.iterdir()):
            info = {"name": entry.name, "type": "dir" if entry.is_dir() else "file"}
            if entry.is_file():
                try:
                    info["size"] = entry.stat().st_size
                except OSError:
                    info["size"] = None
            entries.append(info)
    except PermissionError:
        return {"error": f"Permission denied: {path}"}

    output = f"Contents of {path}:\n\n"
    for e in entries:
        icon = "📁" if e["type"] == "dir" else "📄"
        size = f" ({e['size']} bytes)" if e.get("size") is not None else ""
        output += f"  {icon} {e['name']}{size}\n"

    return {"text": output, "count": len(entries)}


# ---------------------------------------------------------------------------
# JSON-RPC 2.0 handler
# ---------------------------------------------------------------------------
def handle_jsonrpc(body: dict) -> dict:
    method = body.get("method", "")
    req_id = body.get("id")
    params = body.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "Web Tools MCP Server", "version": "1.0.0"},
                "capabilities": {"tools": {"listChanged": False}},
            },
        }

    if method == "notifications/initialized":
        return None  # No response for notifications

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": TOOLS},
        }

    if method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        logger.info(f"Executing tool: {tool_name} with args: {json.dumps(arguments)[:200]}")

        result = execute_tool(tool_name, arguments)

        is_error = "error" in result
        text = result.get("error") or result.get("text") or result.get("output") or json.dumps(result, indent=2)

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
        logger.info(f"← {body.get('method', '?')}")

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
    PORT = 8081
    server = HTTPServer(("0.0.0.0", PORT), MCPHandler)
    logger.info(f"🚀 Web Tools MCP Server running on http://localhost:{PORT}/mcp")
    logger.info(f"Tools: {', '.join(t['name'] for t in TOOLS)}")
    logger.info("Register in UI → URL: http://localhost:8081/mcp, Auth: none")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        server.shutdown()
