from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace
from typing import Any, cast

from networkx.utils import UnionFind

from biotope.graph.contracts import Evidence, GraphRecord, Identity, Match, Pipeline, Precedence
from biotope.graph.sources import digest
from biotope.graph.topology import ConceptSchema, concept_id, field_names, hints, identifier, property_type


Check = Callable[[str, object, ConceptSchema], None]
KeyValue = tuple[str, str]
Report = dict[str, Any]


@dataclass
class Copy:
    value: object
    record: str | None
    evidence: set[Evidence]
    mappings: set[str]
    sources: set[str]


@dataclass(eq=False)
class Link:
    match: Match
    evidence: set[Evidence]
    mappings: set[str]
    subject: list[str] = field(default_factory=list[str])
    object: list[str] = field(default_factory=list[str])

    def describe(self) -> dict[str, str]:
        return {
            "subject_id": self.match.subject_id,
            "object_id": self.match.object_id,
            "mapping_justification": self.match.mapping_justification,
        }


@dataclass
class Entity:
    concept: str
    copies: list[Copy]
    keys: dict[str, set[str]]
    kept_apart: bool = False
    automatic: list[Link] = field(default_factory=list[Link])
    id: str = ""
    derived: bool = False

    @property
    def records(self) -> list[str]:
        return sorted({copy.record for copy in self.copies if copy.record is not None})


@dataclass
class Contradiction:
    concept: str
    keys: dict[str, list[str]]
    whole: list[Entity]
    apart: list[Entity]
    links: list[Link]

    def describe(self) -> Report:
        return {
            "concept": self.concept,
            "keys": self.keys,
            "entities": sorted(entity.id for entity in self.whole),
            "apart": [
                *({"record": entity.records[0], "entity": entity.id} for entity in self.apart),
                *({"link": link.describe()} for link in self.links),
            ],
        }


@dataclass
class Resolution:
    nodes: dict[str, GraphRecord]
    edges: dict[str, GraphRecord]
    report: Report
    entities: list[Report]
    relations: list[Report]


def frozen(value: object) -> object:
    return tuple(cast(list[object], value)) if isinstance(value, list) else value


def given(value: object) -> bool:
    return value is not None and value != "" and value != []


def key_values(value: object, name: str) -> set[str]:
    found: object = getattr(value, name)
    items = cast(list[object], found) if isinstance(found, list) else [found]
    return {item for item in items if isinstance(item, str) and item}


def rank(copy: Copy, order: tuple[str, ...]) -> int | None:
    return min((order.index(source) for source in copy.sources if source in order), default=None)


def label(copy: Copy, order: tuple[str, ...]) -> str:
    place = rank(copy, order)
    return order[place] if place is not None else ", ".join(sorted(copy.sources)) or "an untracked source"


def ordered(copies: Iterable[Copy], order: tuple[str, ...] = ()) -> list[Copy]:
    def position(copy: Copy) -> tuple[object, ...]:
        place = rank(copy, order)
        values = [frozen(getattr(copy.value, name)) for name in field_names(type(copy.value))]
        return (len(order) if place is None else place, copy.record or "", sorted(copy.mappings), repr(values))

    return sorted(copies, key=position)


class Fields:
    def __init__(self, subject: Report, named: str, rule: Precedence | None, conflicts: list[Report]) -> None:
        self.subject = subject
        self.named = named
        self.rule = rule
        self.conflicts = conflicts

    def merge(self, copies: list[Copy], fixed: tuple[str, ...]) -> tuple[dict[str, object], dict[str, Report]]:
        chosen: dict[str, object] = {}
        entries: dict[str, Report] = {}
        for name in field_names(type(copies[0].value)):
            if name not in fixed:
                chosen[name], entries[name] = self.choose(name, copies)
        return chosen, entries

    def entry(self, value: object, holders: list[Copy]) -> Report:
        found: Report = {"value": value, "sources": sorted({source for copy in holders for source in copy.sources})}
        if "entity" in self.subject:
            found["records"] = sorted({copy.record for copy in holders if copy.record is not None})
        return found

    def choose(self, name: str, copies: list[Copy]) -> tuple[object, Report]:
        rule = self.rule
        order = tuple(source.name for source in rule.fields.get(name, ())) if rule is not None else ()
        ranked = ordered(copies, order)
        holders = [copy for copy in ranked if given(getattr(copy.value, name))]
        if not holders:
            value = getattr(ranked[0].value, name)
            return value, self.entry(value, [])
        if rule is not None and name in rule.combine:
            items: list[object] = []
            for copy in holders:
                items.extend(item for item in cast(list[object], getattr(copy.value, name)) if item not in items)
            return items, self.entry(items, holders)
        value = getattr(holders[0].value, name)
        agreeing = [copy for copy in holders if frozen(getattr(copy.value, name)) == frozen(value)]
        if len(agreeing) < len(holders):
            self.conflict(name, order, holders, value)
        return value, self.entry(value, agreeing)

    def conflict(self, name: str, order: tuple[str, ...], holders: list[Copy], value: object) -> None:
        entity = "entity" in self.subject
        values = sorted(
            {
                (label(copy, order), copy.record or "", repr(frozen(getattr(copy.value, name)))): {
                    "source": label(copy, order),
                    **({"record": copy.record} if entity else {}),
                    "value": getattr(copy.value, name),
                }
                for copy in holders
            }.items()
        )
        listed = [item for _, item in values]
        shown = "; ".join(
            f"{item['value']!r} from {item['source']}" + (f" ({item['record']})" if entity else "") for item in listed
        )
        if not order:
            raise ValueError(
                f"{self.named}: sources disagree on {name!r} and no precedence is declared for it: {shown}. "
                "Declare the field's precedence in graph/alignment"
            )
        unlisted = sorted({label(copy, order) for copy in holders if rank(copy, order) is None})
        if unlisted:
            raise ValueError(
                f"{self.named}: {', '.join(unlisted)} give a value of {name!r} but are not in its precedence "
                f"list ({', '.join(order)}): {shown}"
            )
        self.conflicts.append(
            {
                **self.subject,
                "field": name,
                "values": listed,
                "chosen": value,
                "chosen_source": label(holders[0], order),
            }
        )


class Partition:
    def __init__(self, keys: dict[str, set[KeyValue]], links: list[Link], single: set[str]) -> None:
        self.keys = keys
        self.links = links
        self.single = single

    def parts(self, records: Iterable[str], links: Iterable[Link]) -> list[set[str]]:
        kept = sorted(records)
        found = UnionFind(kept)
        holders: dict[KeyValue, list[str]] = {}
        for record in kept:
            for item in self.keys[record]:
                holders.setdefault(item, []).append(record)
        for group in holders.values():
            found.union(*group)
        present = set(kept)
        for link in links:
            ends = [
                next((record for record in side if record in present), None) for side in (link.subject, link.object)
            ]
            if ends[0] is not None and ends[1] is not None:
                found.union(ends[0], ends[1])
        return sorted((set(group) for group in found.to_sets()), key=min)

    def contradicted(self, group: Iterable[str]) -> dict[str, list[str]]:
        found: dict[str, list[str]] = {}
        for name in sorted(self.single):
            values = sorted({value for record in group for key, value in self.keys[record] if key == name})
            if len(values) > 1:
                found[name] = values
        return found

    def score(self, groups: list[set[str]]) -> int:
        return sum(len(values) - 1 for group in groups for values in self.contradicted(group).values())

    def clash(self, first: str, second: str) -> bool:
        own = {key: value for key, value in self.keys[first] if key in self.single}
        return any(key in own and own[key] != value for key, value in self.keys[second] if key in self.single)

    def ends(self, link: Link, records: set[str]) -> tuple[list[str], list[str]]:
        return [r for r in link.subject if r in records], [r for r in link.object if r in records]

    def clashes(self, choice: Link | str, records: set[str], links: list[Link]) -> int:
        if isinstance(choice, Link):
            subject, target = self.ends(choice, records)
            return int(any(self.clash(first, second) for first in subject for second in target))
        neighbours = {other for other in records if self.keys[other] & self.keys[choice]}
        for link in links:
            subject, target = self.ends(link, records)
            if choice in subject or choice in target:
                neighbours.update(subject[:1] + target[:1])
        return sum(self.clash(choice, other) for other in neighbours - {choice})

    def split(self, group: set[str], links: list[Link]) -> tuple[list[set[str]], list[str], list[Link]]:
        records, kept = set(group), list(links)
        apart: list[str] = []
        dropped: list[Link] = []
        while True:
            current = self.parts(records, kept)
            total = self.score(current)
            if total == 0:
                return current, sorted(apart), dropped
            options: list[tuple[tuple[int, int, int, int, str], Link | str]] = []
            for link in kept:
                after = self.parts(records, [item for item in kept if item is not link])
                name = f"{link.match.subject_id} {link.match.object_id}"
                rank = (self.score(after), -self.clashes(link, records, kept), 0, -pairs(after), name)
                options.append((rank, link))
            for record in sorted(records):
                after = self.parts(records - {record}, kept)
                rank = (self.score(after), -self.clashes(record, records, kept), 1, -pairs(after), record)
                options.append((rank, record))
            best, choice = min(options, key=lambda option: option[0])
            if best[0] >= total:
                for part in current:
                    if self.contradicted(part):
                        apart.extend(part)
                        records -= part
            elif isinstance(choice, Link):
                kept.remove(choice)
                dropped.append(choice)
            else:
                records.remove(choice)
                apart.append(choice)


def pairs(groups: list[set[str]]) -> int:
    return sum(len(group) * (len(group) - 1) // 2 for group in groups)


class Resolver:
    def __init__(self, pipeline: Pipeline, schema: dict[str, ConceptSchema], check: Check | None) -> None:
        self.schema = schema
        self.identities = {concept_id(item.concept): item for item in pipeline.identities}
        self.precedence = {concept_id(item.concept): item for item in pipeline.precedence}
        self.check = check
        self.conflicts: list[Report] = []
        self.contradictions: list[Contradiction] = []
        self.unresolved: list[Report] = []
        self.references: dict[str, dict[str, list[Entity]]] = {}

    def resolve(self, nodes: list[Copy], edges: list[Copy], links: list[Link]) -> Resolution:
        by_concept: dict[str, list[Copy]] = {}
        for copy in nodes:
            by_concept.setdefault(concept_id(type(copy.value)), []).append(copy)
        entities: list[Entity] = []
        for concept in sorted(by_concept):
            declared = self.identities.get(concept)
            concept_links = [link for link in links if link.match.concept == concept]
            if declared is None:
                entities.extend(self.plain(concept, by_concept[concept]))
            else:
                entities.extend(self.identified(concept, declared, by_concept[concept], concept_links))
        owners: dict[str, str] = {}
        for entity in entities:
            if entity.id in owners:
                raise ValueError(
                    f"{entity.id}: two entities share this ID, of {owners[entity.id]} and {entity.concept}"
                )
            owners[entity.id] = entity.concept
            table = self.references.setdefault(entity.concept, {})
            keys = (f"{key}:{value}" for key, values in entity.keys.items() for value in values)
            for name in {entity.id, *entity.records, *keys}:
                table.setdefault(name, []).append(entity)
        merged_nodes, described = self.nodes(entities)
        merged_edges, relations = self.edges(edges)
        return Resolution(merged_nodes, merged_edges, self.report(entities), described, relations)

    def report(self, entities: list[Entity]) -> Report:
        summary: dict[str, dict[str, int]] = {}
        for entity in entities:
            counts = summary.setdefault(entity.concept, {"entities": 0, "records": 0, "merged": 0, "derived_ids": 0})
            counts["entities"] += 1
            counts["records"] += len(entity.records)
            counts["merged"] += len(entity.records) > 1
            counts["derived_ids"] += entity.derived
        automatic = [
            {"concept": entity.concept, "entity": entity.id, **link.describe()}
            for entity in entities
            for link in entity.automatic
        ]
        return {
            "entities": dict(sorted(summary.items())),
            "contradictions": sorted(
                (item.describe() for item in self.contradictions), key=lambda item: (item["concept"], item["entities"])
            ),
            "conflicts": sorted(
                self.conflicts,
                key=lambda item: (item["concept"], repr(item.get("entity")), repr(item.get("relation")), item["field"]),
            ),
            "automatic_merges": sorted(automatic, key=lambda item: sorted(item.items())),
            "unresolved_links": sorted(self.unresolved, key=lambda item: sorted(item.items())),
        }

    def plain(self, concept: str, copies: list[Copy]) -> list[Entity]:
        records: dict[str, list[Copy]] = {}
        for copy in copies:
            records.setdefault(copy.record or "", []).append(copy)
        return [Entity(concept, group, {}, id=record) for record, group in sorted(records.items())]

    def identified(self, concept: str, declared: Identity, copies: list[Copy], links: list[Link]) -> list[Entity]:
        records: dict[str, list[Copy]] = {}
        for copy in copies:
            records.setdefault(copy.record or "", []).append(copy)
        keys = {
            record: {
                (key.name, value)
                for copy in group
                for key in declared.keys
                for value in key_values(copy.value, key.name)
            }
            for record, group in records.items()
        }
        references: dict[str, list[str]] = {record: [record] for record in records}
        for record, items in sorted(keys.items()):
            for name, value in sorted(items):
                references.setdefault(f"{name}:{value}", []).append(record)
        applied: list[Link] = []
        for link in sorted(links, key=lambda item: sorted(item.describe().items())):
            subject, target = references.get(link.match.subject_id), references.get(link.match.object_id)
            if subject is None or target is None:
                missing = [
                    name
                    for name, found in ((link.match.subject_id, subject), (link.match.object_id, target))
                    if not found
                ]
                self.unresolved.append({"concept": concept, **link.describe(), "missing": missing})
            else:
                applied.append(replace(link, subject=subject, object=target))
        partition = Partition(keys, applied, {key.name for key in declared.keys if key.single})
        by_keys = {record: index for index, group in enumerate(partition.parts(records, [])) for record in group}
        result: list[Entity] = []
        for group in partition.parts(records, applied):
            inside = [link for link in applied if link.subject[0] in group]
            contradicted = partition.contradicted(group)
            parts, apart, dropped = partition.split(group, inside) if contradicted else ([group], [], [])
            whole = [self.entity(concept, part, records, keys) for part in parts]
            for entity in whole:
                for link in inside:
                    first = next((record for record in link.subject if record in entity.records), None)
                    second = next((record for record in link.object if record in entity.records), None)
                    if link in dropped or first is None or second is None:
                        continue
                    if by_keys[first] != by_keys[second]:
                        entity.automatic.append(link)
            separate = [self.entity(concept, {record}, records, keys, kept_apart=True) for record in apart]
            result += [*whole, *separate]
            if contradicted:
                self.contradictions.append(Contradiction(concept, contradicted, whole, separate, dropped))
        for entity in result:
            natural = sorted(entity.keys.get(declared.natural, set())) if declared.natural else []
            if len(natural) == 1 and not entity.kept_apart:
                entity.id = identifier(f"{declared.natural}:{natural[0]}")
            else:
                entity.id, entity.derived = f"{concept}-{digest(entity.records)[:16]}", True
        return result

    def entity(
        self,
        concept: str,
        group: set[str],
        records: dict[str, list[Copy]],
        keys: dict[str, set[KeyValue]],
        *,
        kept_apart: bool = False,
    ) -> Entity:
        values: dict[str, set[str]] = {}
        for name, value in (item for record in group for item in keys[record]):
            values.setdefault(name, set()).add(value)
        copies = [copy for record in sorted(group) for copy in records[record]]
        return Entity(concept, copies, values, kept_apart=kept_apart)

    def lookup(self, concept: str, reference: str) -> Entity | None:
        found = self.references.get(concept, {}).get(reference, [])
        if len(found) > 1:
            found = [entity for entity in found if not entity.kept_apart] or found
        if len(found) > 1:
            names = ", ".join(sorted(entity.id for entity in found))
            raise ValueError(f"{reference!r} names several {concept} entities: {names}")
        return found[0] if found else None

    def nodes(self, entities: list[Entity]) -> tuple[dict[str, GraphRecord], list[Report]]:
        stored: dict[str, GraphRecord] = {}
        described: list[Report] = []
        for entity in sorted(entities, key=lambda item: (item.concept, item.id)):
            subject = {"concept": entity.concept, "entity": entity.id}
            fields = Fields(
                subject, f"{entity.concept} {entity.id}", self.precedence.get(entity.concept), self.conflicts
            )
            chosen, entries = fields.merge(entity.copies, ("id",))
            value = replace(cast(Any, ordered(entity.copies)[0].value), id=entity.id, **chosen)
            if self.check is not None and entity.concept in self.identities:
                self.check(entity.id, value, self.schema[entity.concept])
            parts = [*entity.copies, *entity.automatic]
            evidence = {item for part in parts for item in part.evidence}
            stored[entity.id] = GraphRecord(value, evidence, {item for part in parts for item in part.mappings})
            described.append(
                {
                    "concept": entity.concept,
                    "id": entity.id,
                    "derived": entity.derived,
                    "kept_apart": entity.kept_apart,
                    "records": [
                        {
                            "id": record,
                            "sources": sorted(
                                {s for copy in entity.copies if copy.record == record for s in copy.sources}
                            ),
                            "mappings": sorted(
                                {m for copy in entity.copies if copy.record == record for m in copy.mappings}
                            ),
                        }
                        for record in entity.records
                    ],
                    "keys": {name: sorted(values) for name, values in sorted(entity.keys.items())},
                    "fields": entries,
                    "automatic": sorted(
                        (link.describe() for link in entity.automatic), key=lambda item: sorted(item.items())
                    ),
                }
            )
        return stored, described

    def endpoints(self, copy: Copy) -> tuple[str, str]:
        semantic = concept_id(type(copy.value))
        ends: list[str] = []
        for endpoint in ("source", "target"):
            expected = self.schema[semantic][endpoint] or ""
            reference = getattr(copy.value, endpoint)
            entity = self.lookup(expected, reference)
            if entity is None:
                raise ValueError(f"{semantic} {reference}: unresolved {endpoint} {reference!r}; expected {expected}")
            ends.append(entity.id)
        return ends[0], ends[1]

    def edges(self, edges: list[Copy]) -> tuple[dict[str, GraphRecord], list[Report]]:
        groups: dict[str, list[tuple[tuple[str, str], Copy]]] = {}
        for copy in edges:
            ends = self.endpoints(copy)
            semantic = concept_id(type(copy.value))
            keyed = "id" in field_names(type(copy.value))
            identity = identifier(getattr(copy.value, "id")) if keyed else "edge:" + digest([semantic, *ends])
            groups.setdefault(identity, []).append((ends, copy))
        stored: dict[str, GraphRecord] = {}
        relations: list[Report] = []
        for identity, group in sorted(groups.items()):
            (source, target), copies = group[0][0], [copy for _, copy in group]
            semantic = concept_id(type(copies[0].value))
            if any(ends != (source, target) for ends, _ in group):
                found = sorted({ends for ends, _ in group})
                raise ValueError(f"{semantic} {identity}: its copies resolve to different endpoints: {found}")
            relation: Report = {"source": source, "target": target}
            if "id" in field_names(type(copies[0].value)):
                relation = {"id": identity, **relation}
            named = f"{semantic} {source} -> {target}"
            fields = Fields(
                {"concept": semantic, "relation": relation}, named, self.precedence.get(semantic), self.conflicts
            )
            chosen, entries = fields.merge(copies, ("id", "source", "target"))
            value = replace(cast(Any, ordered(copies)[0].value), source=source, target=target, **chosen)
            if self.check is not None:
                self.check(identity, value, self.schema[semantic])
            evidence = {item for copy in copies for item in copy.evidence}
            stored[identity] = GraphRecord(value, evidence, {item for copy in copies for item in copy.mappings})
            relations.append(
                {
                    "concept": semantic,
                    "id": identity,
                    "source": source,
                    "target": target,
                    "sources": sorted({item for copy in copies for item in copy.sources}),
                    "fields": entries,
                }
            )
        return stored, relations


@dataclass
class Alignment:
    identities: dict[str, Report] = field(default_factory=dict[str, Report])
    precedence: dict[str, Report] = field(default_factory=dict[str, Report])
    problems: list[tuple[str, str]] = field(default_factory=list[tuple[str, str]])


def kind(cls: type, name: str) -> str | None:
    try:
        return property_type(hints(cls)[name])
    except (KeyError, ValueError):
        return None


def check_alignment(pipeline: Pipeline) -> Alignment:
    found = Alignment()
    nodes, edges = pipeline.topology.nodes, pipeline.topology.edges
    for declared in pipeline.identities:
        concept = str(getattr(declared.concept, "schema_id", declared.concept))
        problems: list[str] = []
        if declared.concept not in nodes:
            problems.append("an identity declaration needs a node concept of the topology")
        elif concept in found.identities:
            problems.append("has two identity declarations")
        names = [key.name for key in declared.keys]
        problems += [f"key {name!r} is declared twice" for name in sorted({n for n in names if names.count(n) > 1})]
        for key in declared.keys:
            if key.name == "id" or key.name not in field_names(declared.concept):
                problems.append(f"key {key.name!r} names no field of {declared.concept.__name__}; keys are fields")
            elif kind(declared.concept, key.name) not in (("str",) if key.single else ("str", "str[]")):
                allowed = "a str or str | None field" if key.single else "a str or list[str] field, or either | None"
                problems.append(f"key {key.name!r} is {'single' if key.single else 'multi'}-valued and needs {allowed}")
        if declared.natural is not None and declared.natural not in [key.name for key in declared.keys if key.single]:
            problems.append(f"natural key {declared.natural!r} must be one of its single-valued keys")
        found.problems += [(concept, f"{concept}: {problem}") for problem in problems]
        found.identities[concept] = {
            "keys": {key.name: "single" if key.single else "multiple" for key in declared.keys},
            "natural": declared.natural,
        }
    for declared in pipeline.precedence:
        concept = str(getattr(declared.concept, "schema_id", declared.concept))
        problems = []
        if declared.concept not in (*nodes, *edges):
            problems.append("a precedence declaration needs a concept of the topology")
        elif concept in found.precedence:
            problems.append("has two precedence declarations")
        fixed = ("id", "source", "target") if declared.concept in edges else ("id",)
        properties = [name for name in field_names(declared.concept) if name not in fixed]
        for name, order in declared.fields.items():
            if name not in properties:
                problems.append(f"field {name!r} is not a property of {declared.concept.__name__}")
            unselected = [source.name for source in order if source not in pipeline.sources]
            if unselected:
                problems.append(f"field {name!r} lists sources the pipeline does not select: {', '.join(unselected)}")
            if len({source.name for source in order}) != len(order):
                problems.append(f"field {name!r} lists a source twice")
        for name in declared.combine:
            if name not in properties or kind(declared.concept, name) != "str[]":
                problems.append(f"combined field {name!r} needs a list[str] property")
        found.problems += [(concept, f"{concept}: {problem}") for problem in problems]
        found.precedence[concept] = {
            "fields": {name: [source.name for source in order] for name, order in declared.fields.items()},
            "combine": list(declared.combine),
        }
    return found
