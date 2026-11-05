"""Selected graph concepts, matching the scaffold's registry convention."""

from biotope.graph import Topology

from .person.node import Person
from .sample.from_person import FromPerson
from .sample.node import Sample


TOPOLOGY = Topology(nodes=(Sample, Person), edges=(FromPerson,))
