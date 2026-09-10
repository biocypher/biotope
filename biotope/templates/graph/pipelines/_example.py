"""Wiring example for build_graph.build; inactive until adapted and registered."""

from biotope.graph import RunContext, SourceRecord

from ..mappings._example import MAPPING, NORMALISE, ExampleValue
from ..sources._example.example_rows import SOURCE
from ..sources._example.example_rows.loader import Config, load


def map_records(context: RunContext, config: Config) -> None:
    """Normalize first, then construct graph objects from the buffered intermediates.

    Buffer the intermediate record type itself. A list of typed
    ``SourceRecord[...]`` keeps its element type, so the later ``context.map``
    call is still checked; a buffer of untyped mapping/record pairs would have to
    be recovered with casts and would check nothing.
    """
    values: list[SourceRecord[ExampleValue]] = []
    for record in context.load(SOURCE, load, config):
        values.extend(context.apply(NORMALISE, record))
    for value in values:
        context.map(MAPPING, value)
