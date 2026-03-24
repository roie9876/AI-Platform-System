import json

import click
import httpx
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from cli.commands.auth import load_credentials

console = Console()


@click.group()
def agent():
    """Agent management commands."""
    pass


@agent.command(name="list")
@click.pass_context
def list_agents(ctx):
    """List available agents."""
    base_url, headers, cookies = load_credentials()
    try:
        resp = httpx.get(
            f"{base_url}/api/v1/agents",
            headers=headers,
            cookies=cookies,
            timeout=30,
        )
        if resp.status_code == 401:
            click.echo("Session expired. Run: aiplatform auth login", err=True)
            raise SystemExit(1)
        resp.raise_for_status()
        data = resp.json()
        agents = data.get("agents", data) if isinstance(data, dict) else data

        table = Table(title="Agents")
        table.add_column("ID", style="dim")
        table.add_column("Name", style="bold")
        table.add_column("Status")
        table.add_column("Description", max_width=40)

        for a in agents:
            table.add_row(
                str(a["id"]),
                a["name"],
                a.get("status", ""),
                (a.get("description") or "")[:40],
            )
        console.print(table)
    except httpx.ConnectError:
        click.echo(f"Cannot connect to {base_url}", err=True)
        raise SystemExit(1)


@agent.command()
@click.argument("agent_id")
@click.option("-m", "--message", required=True, help="Message to send to the agent")
@click.option("--thread-id", default=None, help="Reuse an existing thread")
@click.option("--json-output", is_flag=True, help="Output raw JSON instead of formatted text")
@click.pass_context
def run(ctx, agent_id, message, thread_id, json_output):
    """Run an agent with a message."""
    base_url, headers, cookies = load_credentials()

    try:
        # Create a new thread if not provided
        if not thread_id:
            resp = httpx.post(
                f"{base_url}/api/v1/threads",
                headers=headers,
                cookies=cookies,
                json={"agent_id": agent_id},
                timeout=30,
            )
            if resp.status_code == 401:
                click.echo("Session expired. Run: aiplatform auth login", err=True)
                raise SystemExit(1)
            resp.raise_for_status()
            thread_id = resp.json()["id"]

        # Send message via chat endpoint (SSE streaming)
        with httpx.stream(
            "POST",
            f"{base_url}/api/v1/agents/{agent_id}/chat",
            headers=headers,
            cookies=cookies,
            json={"message": message, "thread_id": thread_id},
            timeout=120,
        ) as resp:
            if resp.status_code == 401:
                click.echo("Session expired. Run: aiplatform auth login", err=True)
                raise SystemExit(1)
            if resp.status_code == 404:
                click.echo("Agent not found", err=True)
                raise SystemExit(1)
            resp.raise_for_status()

            full_response = []
            for line in resp.iter_lines():
                if not line or not line.startswith("data: "):
                    continue
                payload = line[6:]
                if payload == "[DONE]":
                    break
                try:
                    event = json.loads(payload)
                    if event.get("type") == "content":
                        chunk = event.get("content", "")
                        full_response.append(chunk)
                        if not json_output:
                            click.echo(chunk, nl=False)
                    elif event.get("type") == "error":
                        click.echo(f"\nError: {event.get('content', 'Unknown error')}", err=True)
                        raise SystemExit(1)
                except json.JSONDecodeError:
                    continue

            if json_output:
                click.echo(json.dumps({"response": "".join(full_response), "thread_id": thread_id}))
            else:
                click.echo(f"\n\nThread: {thread_id}")

    except httpx.ConnectError:
        click.echo(f"Cannot connect to {base_url}", err=True)
        raise SystemExit(1)
