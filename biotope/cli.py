"""Command line interface for biotope."""

import click

from biotope.commands.add import add as add_cmd
from biotope.commands.annotate import annotate as annotate_cmd
from biotope.commands.chat import chat as chat_cmd
from biotope.commands.check_data import check_data as check_data_cmd
from biotope.commands.commit import commit as commit_cmd
from biotope.commands.config import config as config_cmd
from biotope.commands.get import get as get_cmd
from biotope.commands.init import init as init_cmd
from biotope.commands.log import log as log_cmd
from biotope.commands.mv import mv as mv_cmd
from biotope.commands.pull import pull as pull_cmd
from biotope.commands.push import push as push_cmd
from biotope.commands.read import read as read_cmd
from biotope.commands.status import status as status_cmd


@click.group()
@click.version_option(version="0.4.2")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """CLI entrypoint."""
    ctx.ensure_object(dict)
    ctx.obj = {"version": "0.3.0"}


cli.add_command(init_cmd, "init")


@cli.command()
def build() -> None:
    """Build knowledge representation."""
    click.echo("Building knowledge representation...")


cli.add_command(read_cmd, "read")


cli.add_command(chat_cmd, "chat")


cli.add_command(annotate_cmd, "annotate")
cli.add_command(get_cmd, "get")

# Git-inspired version control commands
cli.add_command(add_cmd, "add")
cli.add_command(mv_cmd, "mv")
cli.add_command(status_cmd, "status")
cli.add_command(commit_cmd, "commit")
cli.add_command(log_cmd, "log")
cli.add_command(push_cmd, "push")
cli.add_command(pull_cmd, "pull")
cli.add_command(check_data_cmd, "check-data")

# Configuration commands
cli.add_command(config_cmd, "config")


@cli.command()
def benchmark() -> None:
    """Run the BioCypher ecosystem benchmarks."""
    click.echo("Running benchmarks...")


@cli.command()
def view() -> None:
    """View and analyze BioCypher knowledge graphs."""
    click.echo("Viewing knowledge graph...")


if __name__ == "__main__":
    cli()
