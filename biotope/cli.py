"""Command line interface for biotope."""

import click

from biotope._version import __version__
from biotope.commands.add import add as add_cmd
from biotope.commands.annotate import annotate as annotate_cmd
from biotope.commands.check_data import check_data as check_data_cmd
from biotope.commands.commit import commit as commit_cmd
from biotope.commands.config import config as config_cmd
from biotope.commands.init import init as init_cmd
from biotope.commands.log import log as log_cmd
from biotope.commands.map import map_group as map_cmd
from biotope.commands.mark import mark as mark_cmd
from biotope.commands.mv import mv as mv_cmd
from biotope.commands.propose_alignment import propose_alignment as propose_alignment_cmd
from biotope.commands.propose_mapping import propose_mapping as propose_mapping_cmd
from biotope.commands.pull import pull as pull_cmd
from biotope.commands.push import push as push_cmd
from biotope.commands.queue import queue as queue_cmd
from biotope.commands.rm import rm as rm_cmd
from biotope.commands.status import status as status_cmd
from biotope.croissant.mapping.loader import MappingLoadError


class _CLIGroup(click.Group):
    """Present mapping input errors consistently across retained commands."""

    def invoke(self, ctx: click.Context):
        try:
            return super().invoke(ctx)
        except MappingLoadError as exc:
            raise click.ClickException(str(exc)) from exc


@click.group(cls=_CLIGroup)
@click.version_option(version=__version__, prog_name="biotope")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """biotope: Croissant-driven knowledge-graph projects for the BioCypher ecosystem."""
    ctx.ensure_object(dict)
    ctx.obj = {"version": __version__}


# Project lifecycle
cli.add_command(init_cmd, "init")

# Semantic mapping (intent capture + wizard + inspect/scaffold/preview)
cli.add_command(map_cmd, "map")

# Content-level workflow
cli.add_command(propose_mapping_cmd, "propose-mapping")
cli.add_command(propose_alignment_cmd, "propose-alignment")
cli.add_command(queue_cmd, "queue")
cli.add_command(mark_cmd, "mark")

# Metadata annotations
cli.add_command(annotate_cmd, "annotate")

# Git-inspired version control commands
cli.add_command(add_cmd, "add")
cli.add_command(mv_cmd, "mv")
cli.add_command(rm_cmd, "rm")
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
