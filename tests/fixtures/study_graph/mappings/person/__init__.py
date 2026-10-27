from collections.abc import Iterator

from biotope.graph import Mapping, SourceRecord

from ...sources.study.push_people_csv_people.schema import PushPeopleCsvPeople
from ...topology.person.node import Person, PersonId


def map_person(person: SourceRecord[PushPeopleCsvPeople]) -> Iterator[Person]:
    yield Person(id=PersonId(f"study:{person.value.person_id}"), name=person.value.name or "")


MAPPING = Mapping(name="study:person", function=map_person, evidence=("Synthetic people.",))
