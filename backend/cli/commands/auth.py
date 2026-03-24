import json
from pathlib import Path

import click
import httpx

CONFIG_DIR = Path.home() / ".aiplatform"
CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"


@click.group()
def auth():
    """Authentication commands."""
    pass


@auth.command()
@click.option("--email", prompt=True)
@click.option("--password", prompt=True, hide_input=True)
@click.pass_context
def login(ctx, email, password):
    """Log in to the AI Platform."""
    base_url = ctx.obj["base_url"]
    try:
        resp = httpx.post(
            f"{base_url}/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        resp.raise_for_status()
        data = resp.json()
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        cookies = dict(resp.cookies)
        CREDENTIALS_FILE.write_text(
            json.dumps(
                {
                    "base_url": base_url,
                    "cookies": cookies,
                    "access_token": data.get("access_token", ""),
                }
            )
        )
        CREDENTIALS_FILE.chmod(0o600)
        click.echo(f"Logged in as {email}")
    except httpx.HTTPStatusError as e:
        click.echo(f"Login failed: {e.response.text}", err=True)
        raise SystemExit(1)
    except httpx.ConnectError:
        click.echo(f"Cannot connect to {base_url}", err=True)
        raise SystemExit(1)


def load_credentials():
    """Load stored credentials. Returns (base_url, headers) or exits."""
    if not CREDENTIALS_FILE.exists():
        click.echo("Not logged in. Run: aiplatform auth login", err=True)
        raise SystemExit(1)
    data = json.loads(CREDENTIALS_FILE.read_text())
    base_url = data.get("base_url", "http://localhost:8000")
    headers = {}
    token = data.get("access_token")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    cookies = data.get("cookies", {})
    return base_url, headers, cookies
