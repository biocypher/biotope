"""Wiring example for build_graph.build; inactive until adapted and registered."""

from biotope.graph import RunContext

from ..mappings._example import MAPPING
from ..sources._example.example_rows import SOURCE
from ..sources._example.example_rows.loader import Config, load


def map_records(context: RunContext, config: Config) -> None:
    """Call with explicit source configuration inside the authored build function."""
    for record in context.load(SOURCE, load, config):
        context.map(MAPPING, record)
