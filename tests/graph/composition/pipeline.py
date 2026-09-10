"""Both sources normalize into one typed buffer, which then builds graph objects."""

from pathlib import Path
from typing import TypeVar

from biotope.graph import Evidence, Pipeline, RunContext, SourceRecord

from .mappings import BUILD_OBJECTS, MAPPINGS, NORMALISE_ASSAY, NORMALISE_LEGACY
from .schema import TOPOLOGY, AssayRow, DonorRow, LegacyRow, Measurement


V = TypeVar("V")

ASSAY_ROWS = (AssayRow("s1", "d1", 1.5), AssayRow("s2", "d2", 2.5))
LEGACY_ROWS = (LegacyRow("s3", "d1", "3.5"), LegacyRow("s4", "unknown", "4.5"))
DONOR_ROWS = (DonorRow("d1", "cohort-a"), DonorRow("d2", "cohort-b"))


def record(value: V, record_set: str, index: int) -> SourceRecord[V]:
    """Stand in for a loader: pair a synthetic value with a resolvable reference."""
    return SourceRecord(value, (Evidence(f"{record_set}.csv", "fixture-v1", record_set, f"row:{index}"),))


def build(context: RunContext) -> None:
    """Normalize both sources into one buffer, then construct graph objects."""
    donors = {row.donor: record(row, "donors", index) for index, row in enumerate(DONOR_ROWS)}
    measurements: list[SourceRecord[Measurement]] = []
    for index, assay in enumerate(ASSAY_ROWS):
        measurements.extend(context.apply(NORMALISE_ASSAY, record(assay, "assay", index)))
    for index, legacy in enumerate(LEGACY_ROWS):
        measurements.extend(context.apply(NORMALISE_LEGACY, record(legacy, "legacy", index)))
    for measurement in measurements:
        donor = donors.get(measurement.value.donor)
        if donor is None:
            context.exclude("unmatched_measurement", measurement.evidence)
            continue
        context.map(BUILD_OBJECTS, measurement, donor=donor)


PIPELINE = Pipeline(
    name="fixture:composition",
    topology=TOPOLOGY,
    sources=(),
    mappings=MAPPINGS,
    run=build,
    scope="Two synthetic sources normalized into one measurement grain.",
    code_paths=tuple(
        Path(__file__).resolve().parent / name for name in ("__init__.py", "schema.py", "mappings.py", "pipeline.py")
    ),
    policies={"unmatched_measurement": "Exclude measurements whose donor is absent from the donor rows."},
    variability="Fixed in-repository synthetic rows; deterministic content.",
)
