"""Command line interface for biotope."""

import click

from biotope.commands.add import add as add_cmd
from biotope.commands.annotate import annotate as annotate_cmd
from biotope.commands.benchmark import benchmark as benchmark_cmd
from biotope.commands.build import build as build_cmd
from biotope.commands.chat import chat as chat_cmd
from biotope.commands.check_data import check_data as check_data_cmd
from biotope.commands.commit import commit as commit_cmd
from biotope.commands.config import config as config_cmd
from biotope.commands.discover import discover as discover_cmd
from biotope.commands.get import get as get_cmd
from biotope.commands.init import init as init_cmd
from biotope.commands.log import log as log_cmd
from biotope.commands.map import map_group as map_cmd
from biotope.commands.mv import mv as mv_cmd
from biotope.commands.propose_alignment import propose_alignment as propose_alignment_cmd
from biotope.commands.propose_mapping import propose_mapping as propose_mapping_cmd
from biotope.commands.pull import pull as pull_cmd
from biotope.commands.push import push as push_cmd
from biotope.commands.read import read as read_cmd
from biotope.commands.search import search as search_cmd
from biotope.commands.status import status as status_cmd
from biotope.commands.view import view as view_cmd


@click.group()
@click.version_option(version="0.5.0")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """biotope: Croissant-driven knowledge-graph projects for the BioCypher ecosystem."""
    ctx.ensure_object(dict)
    ctx.obj = {"version": "0.5.0"}


# Project lifecycle
cli.add_command(init_cmd, "init")

# Semantic mapping (intent capture + wizard + inspect/scaffold/preview)
cli.add_command(map_cmd, "map")

# Content-level workflow
cli.add_command(discover_cmd, "discover")
cli.add_command(propose_mapping_cmd, "propose-mapping")
cli.add_command(propose_alignment_cmd, "propose-alignment")
cli.add_command(build_cmd, "build")
cli.add_command(view_cmd, "view")
cli.add_command(benchmark_cmd, "benchmark")

# Ingestion + NLP
cli.add_command(read_cmd, "read")
cli.add_command(search_cmd, "search")
cli.add_command(get_cmd, "get")
cli.add_command(chat_cmd, "chat")
cli.add_command(annotate_cmd, "annotate")

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


if __name__ == "__main__":
    cli()
