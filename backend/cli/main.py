import click

from cli.commands.auth import auth
from cli.commands.agent import agent


@click.group()
@click.option(
    "--base-url",
    default="http://localhost:8000",
    envvar="AIPLATFORM_URL",
    help="API base URL",
)
@click.pass_context
def cli(ctx, base_url):
    """AI Platform CLI — manage and run agents from the terminal."""
    ctx.ensure_object(dict)
    ctx.obj["base_url"] = base_url


cli.add_command(auth)
cli.add_command(agent)

if __name__ == "__main__":
    cli()
