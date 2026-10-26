from collections.abc import Iterator

from biotope.graph import Mapping, SourceRecord

from ...sources.people.people.schema import People
from ...topology.person.node import Person, PersonId


def map_person(person: SourceRecord[People]) -> Iterator[Person]:
    yield Person(id=PersonId(f"host:{person.value.person_id}"), name=person.value.name or "")


MAPPING = Mapping(name="host:person", function=map_person, evidence=("Synthetic people.",))
