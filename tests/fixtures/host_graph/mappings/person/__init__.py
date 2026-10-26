from collections.abc import Iterator

from biotope.graph import Mapping, SourceRecord

from ...sources.people.people_csv_people.schema import PeopleCsvPeople
from ...topology.person.node import Person, PersonId


def map_person(person: SourceRecord[PeopleCsvPeople]) -> Iterator[Person]:
    yield Person(id=PersonId(f"host:{person.value.person_id}"), name=person.value.name or "")


MAPPING = Mapping(name="host:person", function=map_person, evidence=("Synthetic people.",))
