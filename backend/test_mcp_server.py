"""
Simple test MCP server for local development.

Run with:
    cd backend && source .venv/bin/activate && python test_mcp_server.py

Then register in the UI:
    URL: http://localhost:8080/mcp
    Auth: none

This exposes 3 demo tools:
  - echo: returns whatever text you send
  - add_numbers: adds two numbers
  - get_weather: returns fake weather for a city
"""

import json
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler

SERVER_NAME = "Demo MCP Test Server"
PROTOCOL_VERSION = "2024-11-05"
SESSION_ID = str(uuid.uuid4())

# --- Tool definitions (what gets returned by tools/list) ---

TOOLS = [
    {
        "name": "echo",
        "description": "Echoes back the provided message. Useful for testing.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The message to echo back",
                }
            },
            "required": ["message"],
        },
    },
    {
        "name": "add_numbers",
        "description": "Adds two numbers together and returns the result.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "a": {"type": "number", "description": "First number"},
                "b": {"type": "number", "description": "Second number"},
            },
            "required": ["a", "b"],
        },
    },
    {
        "name": "get_weather",
        "description": "Returns simulated weather data for a given city.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name (e.g. 'Tel Aviv', 'New York')",
                }
            },
            "required": ["city"],
        },
    },
]

# --- Tool implementations ---

FAKE_WEATHER = {
    "tel aviv": {"temp": "28°C", "condition": "Sunny", "humidity": "65%"},
    "new york": {"temp": "18°C", "condition": "Partly Cloudy", "humidity": "55%"},
    "london": {"temp": "14°C", "condition": "Rainy", "humidity": "80%"},
    "tokyo": {"temp": "22°C", "condition": "Clear", "humidity": "50%"},
}


def execute_tool(name: str, arguments: dict) -> list[dict]:
    """Execute a tool and return content blocks."""
    if name == "echo":
        return [{"type": "text", "text": arguments.get("message", "")}]
    elif name == "add_numbers":
        a = arguments.get("a", 0)
        b = arguments.get("b", 0)
        return [{"type": "text", "text": f"{a} + {b} = {a + b}"}]
    elif name == "get_weather":
        city = arguments.get("city", "unknown").lower()
        weather = FAKE_WEATHER.get(city, {"temp": "20°C", "condition": "Unknown", "humidity": "50%"})
        return [{"type": "text", "text": f"Weather in {city.title()}: {weather['temp']}, {weather['condition']}, Humidity: {weather['humidity']}"}]
    else:
        return [{"type": "text", "text": f"Unknown tool: {name}"}]


# --- JSON-RPC handler ---

def handle_jsonrpc(request: dict) -> dict | None:
    """Process a JSON-RPC 2.0 request and return a response."""
    method = request.get("method", "")
    req_id = request.get("id")  # None for notifications
    params = request.get("params", {})

    # Notifications have no id — no response needed
    if req_id is None:
        print(f"  <- Notification: {method}")
        return None

    if method == "initialize":
        result = {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": "1.0.0"},
        }
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        print(f"  -> Calling tool: {tool_name}({arguments})")
        content = execute_tool(tool_name, arguments)
        result = {"content": content, "isError": False}
    else:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }

    return {"jsonrpc": "2.0", "id": req_id, "result": result}


class MCPHandler(BaseHTTPRequestHandler):
    """HTTP handler for MCP JSON-RPC requests."""

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            request = json.loads(body)
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'{"error": "Invalid JSON"}')
            return

        method = request.get("method", "?")
        req_id = request.get("id", "notification")
        print(f"[MCP] {method} (id={req_id})")

        response = handle_jsonrpc(request)

        if response is None:
            # Notification — 204 No Content
            self.send_response(204)
            self.send_header("Mcp-Session-Id", SESSION_ID)
            self.end_headers()
            return

        response_bytes = json.dumps(response).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Mcp-Session-Id", SESSION_ID)
        self.send_header("Content-Length", str(len(response_bytes)))
        self.end_headers()
        self.wfile.write(response_bytes)

    def log_message(self, format, *args):
        # Suppress default access logs — we print our own
        pass


def main():
    host = "0.0.0.0"
    port = 8080
    server = HTTPServer((host, port), MCPHandler)
    print(f"")
    print(f"  MCP Test Server running on http://localhost:{port}/mcp")
    print(f"  Server name: {SERVER_NAME}")
    print(f"  Protocol: {PROTOCOL_VERSION}")
    print(f"")
    print(f"  Available tools:")
    for tool in TOOLS:
        print(f"    - {tool['name']}: {tool['description']}")
    print(f"")
    print(f"  Register in UI with:")
    print(f"    URL:  http://localhost:{port}/mcp")
    print(f"    Auth: none")
    print(f"")
    print(f"  Press Ctrl+C to stop")
    print(f"")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
