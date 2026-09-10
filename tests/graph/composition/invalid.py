"""Every marked line must be rejected by strict static checking.

A trailing "expect" comment names a substring of the required diagnostic. The test
requires an error on each marked line and no error on any other line, so this
file is deliberately excluded from the repository's own type-checked paths.
"""

from biotope.graph import Mapping, RunContext, SourceRecord

from .mappings import BUILD_OBJECTS, MAPPINGS, NORMALISE_ASSAY, NORMALISE_LEGACY, normalise_assay
from .schema import AssayRow, Donor, DonorId, DonorRow, LegacyRow, Measurement, Sample, SampleId, TakenFrom


def arguments(context: RunContext, assay: SourceRecord[AssayRow], legacy: SourceRecord[LegacyRow]) -> None:
    """A1: argument identity, arity and keyword names are checked at the call."""
    context.apply(NORMALISE_ASSAY, legacy)  # expect: "SourceRecord[LegacyRow]"
    context.apply(NORMALISE_LEGACY, assay)  # expect: "SourceRecord[AssayRow]"
    context.apply(NORMALISE_ASSAY, assay.value)  # expect: "AssayRow"
    context.apply(NORMALISE_ASSAY)  # expect: Argument missing for parameter "row"
    context.apply(NORMALISE_ASSAY, assay, legacy)  # expect: Expected 1 positional argument
    context.apply(NORMALISE_ASSAY, source=assay)  # expect: No parameter named "source"


def composition(
    context: RunContext,
    assay: SourceRecord[AssayRow],
    measurement: SourceRecord[Measurement],
    donor: SourceRecord[DonorRow],
) -> None:
    """A1/A2/A3: input order, output precision and the apply/map split."""
    context.map(BUILD_OBJECTS, donor, donor=measurement)  # expect: parameter "measurement"
    context.map(BUILD_OBJECTS, measurement, donor)  # expect: Expected 1 positional argument
    context.map(NORMALISE_ASSAY, assay)  # expect: parameter "mapping"
    produced = context.apply(NORMALISE_ASSAY, assay)
    erased: SourceRecord[AssayRow] = next(iter(produced))  # expect: "SourceRecord[Measurement]"
    collapsed: SourceRecord[Sample] = next(  # expect: "SourceRecord[Sample | Donor | TakenFrom]"
        iter(context.apply(BUILD_OBJECTS, measurement, donor=donor))
    )
    del erased, collapsed


def topology(measurement: SourceRecord[Measurement]) -> None:
    """A3: constructor fields, property types and endpoint identifiers are typed."""
    Sample(id=SampleId("fixture:sample:1"), reading=1.0)  # expect: No parameter named "reading"
    Sample(id=SampleId("fixture:sample:1"), value="1.0")  # expect: parameter "value"
    Sample(id=DonorId("fixture:donor:1"), value=1.0)  # expect: parameter "id"
    TakenFrom(source=DonorId("fixture:donor:1"), target=DonorId("fixture:donor:1"))  # expect: parameter "source"
    Donor(id=DonorId("fixture:donor:1"), cohort=measurement.value.absent)  # expect: Cannot access attribute "absent"


def registration(context: RunContext, assay: SourceRecord[AssayRow]) -> None:
    """A4/A5: no second contract declaration and no unchecked dispatch route."""
    Mapping(name="extra", function=normalise_assay, inputs=(AssayRow,))  # expect: No parameter named "inputs"
    Mapping(name="extra", function=normalise_assay, outputs=(Measurement,))  # expect: No parameter named "outputs"
    MAPPINGS[0].function(assay)  # expect: Cannot access attribute "function"
    context.emit(assay.value, assay.evidence, mapping="gone")  # expect: Cannot access attribute "emit"
