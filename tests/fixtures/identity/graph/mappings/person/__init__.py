from collections.abc import Iterator

from biotope.graph import Mapping, Match, SourceRecord

from ...sources.people.directory.schema import Directory
from ...sources.people.matches.schema import Matches
from ...sources.people.roster.schema import Roster
from ...sources.profile.profile_jsonl.schema import ProfileJsonl
from ...topology.person.node import Person, PersonId


def map_roster(row: SourceRecord[Roster]) -> Iterator[Person]:
    person = row.value
    emails = [person.email] if person.email else []
    yield Person(PersonId(f"roster:{person.record}"), person.name, person.record, person.orcid, emails)


def map_directory(row: SourceRecord[Directory]) -> Iterator[Person]:
    account = row.value
    yield Person(PersonId(f"directory:{account.upn}"), account.name, account.roster, None, [account.upn])


def map_profile(record: SourceRecord[ProfileJsonl]) -> Iterator[Person]:
    values = record.value.values
    emails = [item.value for item in values.emails if item is not None]
    yield Person(PersonId(f"profile:{record.value.id}"), values.name.value, None, values.orcid.value, emails)


def map_match(row: SourceRecord[Matches]) -> Iterator[Match]:
    link = row.value
    yield Match(
        concept=Person.schema_id,
        subject_id=link.subject_id,
        object_id=link.object_id,
        mapping_justification=link.mapping_justification,
        predicate_id=link.predicate_id,
    )


ROSTER_PEOPLE = Mapping(name="fixture:roster-people", function=map_roster, requirements=("entity:person",))
DIRECTORY_PEOPLE = Mapping(name="fixture:directory-people", function=map_directory, requirements=("entity:person",))
PROFILE_PEOPLE = Mapping(name="fixture:profile-people", function=map_profile, requirements=("entity:person",))
PEOPLE_MATCHES = Mapping(name="fixture:people-matches", function=map_match)
