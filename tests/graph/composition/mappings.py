"""Two normalizers sharing one intermediate, then one multi-input graph mapping."""

from collections.abc import Iterator

from biotope.graph import Mapping, MappingEntry, SourceRecord

from .schema import AssayRow, Donor, DonorId, DonorRow, LegacyRow, Measurement, Sample, SampleId, TakenFrom


def normalise_assay(row: SourceRecord[AssayRow]) -> Iterator[Measurement]:
    """Carry the current export into the shared intermediate."""
    yield Measurement(sample=row.value.sample, donor=row.value.donor, value=row.value.reading)


def normalise_legacy(row: SourceRecord[LegacyRow]) -> Iterator[Measurement]:
    """Decode the legacy text reading into that same intermediate."""
    yield Measurement(sample=row.value.sample_code, donor=row.value.donor_code, value=float(row.value.reading))


def build_objects(
    measurement: SourceRecord[Measurement], *, donor: SourceRecord[DonorRow]
) -> tuple[Sample, Donor, TakenFrom]:
    """Mint identities and return the heterogeneous graph objects for one measurement."""
    sample_id = SampleId(f"fixture:sample:{measurement.value.sample}")
    donor_id = DonorId(f"fixture:donor:{donor.value.donor}")
    return (
        Sample(id=sample_id, value=measurement.value.value),
        Donor(id=donor_id, cohort=donor.value.cohort),
        TakenFrom(source=sample_id, target=donor_id),
    )


NORMALISE_ASSAY = Mapping(
    name="fixture:normalise-assay",
    function=normalise_assay,
    evidence=("Synthetic fixture; the export already carries a numeric reading.",),
)

NORMALISE_LEGACY = Mapping(
    name="fixture:normalise-legacy",
    function=normalise_legacy,
    evidence=("Synthetic fixture; legacy text readings are parsed, not rescaled.",),
)

BUILD_OBJECTS = Mapping(
    name="fixture:build-objects",
    function=build_objects,
    requirements=("entity:sample", "entity:donor", "relation:taken_from"),
    evidence=("Synthetic fixture; sample and donor identities are source-local.",),
)

MAPPINGS: tuple[MappingEntry, ...] = (NORMALISE_ASSAY, NORMALISE_LEGACY, BUILD_OBJECTS)
