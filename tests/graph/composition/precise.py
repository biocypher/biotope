"""Composition keeps intermediate and heterogeneous graph types without casts.

Each annotation below is the check: an erased ``SourceRecord[object]`` or a
collapsed output union would not satisfy it. The matching negative cases in
``invalid.py`` rule out an ``Any`` that would satisfy everything.
"""

from collections.abc import Iterator

from biotope.graph import Mapping, RunContext, SourceRecord

from .mappings import BUILD_OBJECTS, NORMALISE_ASSAY, NORMALISE_LEGACY
from .schema import AssayRow, Donor, DonorRow, LegacyRow, Measurement, Sample, TakenFrom


def normalizers_share_one_intermediate(
    context: RunContext, assay: SourceRecord[AssayRow], legacy: SourceRecord[LegacyRow]
) -> list[SourceRecord[Measurement]]:
    """Two unrelated source types converge on one precisely typed intermediate."""
    buffered: list[SourceRecord[Measurement]] = []
    buffered.extend(context.apply(NORMALISE_ASSAY, assay))
    buffered.extend(context.apply(NORMALISE_LEGACY, legacy))
    return buffered


def graph_outputs_stay_heterogeneous(
    context: RunContext, measurement: SourceRecord[Measurement], donor: SourceRecord[DonorRow]
) -> None:
    """A multi-input graph mapping keeps every member of its output union."""
    for produced in context.apply(BUILD_OBJECTS, measurement, donor=donor):
        value: Sample | Donor | TakenFrom = produced.value
        del value
    context.map(BUILD_OBJECTS, measurement, donor=donor)


def reserved_names(*, mapping: SourceRecord[AssayRow], self: SourceRecord[DonorRow]) -> Iterator[Measurement]:
    """A mapping is free to name its inputs after the composition helpers' own parameters."""
    yield Measurement(sample=mapping.value.sample, donor=self.value.donor, value=mapping.value.reading)


RESERVED = Mapping(name="fixture:reserved-names", function=reserved_names)


def reserved_input_names_do_not_collide(
    context: RunContext, assay: SourceRecord[AssayRow], donor: SourceRecord[DonorRow]
) -> list[SourceRecord[Measurement]]:
    """``mapping`` and ``self`` belong to the mapping's signature, not to ``apply``."""
    return list(context.apply(RESERVED, mapping=assay, self=donor))
