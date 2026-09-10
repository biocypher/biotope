"""Synthetic source rows, a shared intermediate and the fixture topology."""

from dataclasses import dataclass
from typing import ClassVar, NewType

from biotope.graph import Topology


@dataclass(frozen=True)
class AssayRow:
    """Stands in for a generated contract over the current assay export."""

    sample: str
    donor: str
    reading: float


@dataclass(frozen=True)
class LegacyRow:
    """A second source of the same measurement, recorded as text."""

    sample_code: str
    donor_code: str
    reading: str


@dataclass(frozen=True)
class DonorRow:
    """Donor attributes arriving from their own record set."""

    donor: str
    cohort: str


@dataclass(frozen=True)
class Measurement:
    """The shared intermediate that both normalizers produce."""

    sample: str
    donor: str
    value: float


SampleId = NewType("SampleId", str)
DonorId = NewType("DonorId", str)


@dataclass(frozen=True)
class Sample:
    """One measured sample, identified within the fixture's own namespace."""

    schema_id: ClassVar[str] = "fixture:sample"
    id: SampleId
    value: float


@dataclass(frozen=True)
class Donor:
    """The donor a sample was taken from."""

    schema_id: ClassVar[str] = "fixture:donor"
    id: DonorId
    cohort: str


@dataclass(frozen=True)
class TakenFrom:
    """Outgoing relation from a sample to its donor."""

    schema_id: ClassVar[str] = "fixture:taken-from"
    source: SampleId
    target: DonorId


TOPOLOGY = Topology(nodes=(Sample, Donor), edges=(TakenFrom,))
