"""Narrow BioCypher integration: local Neo4j import files, without a database."""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict
from pathlib import Path
from typing import Protocol, cast

import yaml

from biotope.graph.runtime import RunContext
from biotope.graph.sources import digest, write_text_atomic
from biotope.graph.topology import concept_id


class GraphWriter(Protocol):
    """An output boundary independent of project source loaders and mappings."""

    def write(self, context: RunContext, directory: Path) -> list[str]:
        """Write validated graph data and return its artifact paths."""
        ...


def _export_labels(concepts: Iterable[str]) -> dict[str, str]:
    # Use readable PascalCase from the complete namespaced ID. Disambiguate only
    # normalization collisions, including the writer's synthetic Entity root.
    bases = {
        semantic: "".join(word.capitalize() for word in re.findall(r"[a-z0-9]+", semantic.lower()))
        for semantic in concepts
    }
    bases = {semantic: base if base and base[0].isalpha() else "Concept" + base for semantic, base in bases.items()}
    counts = Counter(bases.values())
    labels = {
        semantic: base + "H" + digest(semantic)[:10] if counts[base] > 1 or base == "Entity" else base
        for semantic, base in bases.items()
    }
    if len(set(labels.values())) != len(labels):
        raise ValueError("Graph concept IDs collide after export label normalization; use distinct semantic IDs")
    return labels


class BioCypherWriter:
    """Derive a local schema/ontology and write one offline BioCypher format."""

    def write(self, context: RunContext, directory: Path) -> list[str]:
        """Write Neo4j import files and an identity-keyed provenance sidecar."""
        # BioCypher configures disk logging during import, before its per-build
        # configuration is applied. Supply stderr logging first; respect existing handlers.
        logger = logging.getLogger("biocypher")
        if not logger.hasHandlers():
            logger.addHandler(logging.StreamHandler())
            logger.setLevel(logging.INFO)
        try:
            from biocypher import BioCypher
        except ImportError as exc:
            raise ValueError("Install biotope[graph] for BioCypher file output") from exc
        directory.mkdir(parents=True, exist_ok=True)
        for identity, row in (*context.nodes.items(), *context.edges.items()):
            identifiers = [identity]
            if type(row.value) in context.pipeline.topology.edges:
                identifiers += [getattr(row.value, "source"), getattr(row.value, "target")]
            if any(any(char in value for char in ',"|\r\n') for value in identifiers):
                raise ValueError(
                    f"Unsupported BioCypher identifier {identity!r}: "
                    "encode delimiter/quote characters in the project's identity policy"
                )
            property_names = context.schema[concept_id(type(row.value))]["properties"]
            if "preferred_id" in property_names:
                raise ValueError("preferred_id is reserved by BioCypher; rename the graph property")
            for name in property_names:
                value = getattr(row.value, name)
                if isinstance(value, str) and any(char in value for char in "\r\n"):
                    raise ValueError(
                        f"Unsupported multiline BioCypher property {identity}.{name}; "
                        "choose an explicit project representation"
                    )
                if isinstance(value, list) and any(
                    any(char in item for char in "|\r\n") for item in cast(list[str], value)
                ):
                    raise ValueError(f"Unsupported BioCypher string-list separator/newline in {identity}.{name}")
        labels = _export_labels(context.schema)
        schema = {
            labels[semantic]: {
                "represented_as": item["kind"],
                "input_label": semantic,
                "is_a": "entity",
                "properties": item["properties"],
            }
            for semantic, item in context.schema.items()
        }
        for semantic, item in context.schema.items():
            if item["kind"] == "edge":
                source, target = item["source"], item["target"]
                if source is None or target is None:
                    raise ValueError(f"{semantic}: edge topology has no endpoint contracts")
                schema[labels[semantic]]["source"] = labels[source]
                schema[labels[semantic]]["target"] = labels[target]
        schema_path = directory / "schema_config.yaml"
        write_text_atomic(schema_path, yaml.safe_dump(schema, sort_keys=True))
        write_text_atomic(
            directory / "topology.json",
            json.dumps({"concepts": context.schema, "export_labels": labels}, indent=2) + "\n",
        )
        ontology_path = directory / "ontology.ttl"
        # This local root exists only to satisfy the writer's ontology interface.
        # Declared topology supplies every domain concept; no implicit Biolink.
        write_text_atomic(
            ontology_path,
            "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
            '<urn:biotope:entity> a rdfs:Class ; rdfs:label "entity" .\n',
        )
        config_path = directory / "biocypher_config.yaml"
        config = {
            "biocypher": {
                "dbms": "neo4j",
                "offline": True,
                "strict_mode": False,
                "head_ontology": {"url": str(ontology_path.resolve()), "root_node": "entity"},
                "tail_ontologies": {},
                "log_to_disk": False,
                "debug": False,
            },
            "neo4j": {
                "delimiter": ",",
                "array_delimiter": "|",
                "quote_character": '"',
                "labels_order": "Leaves",
                "skip_duplicate_nodes": False,
                "skip_bad_relationships": False,
            },
        }
        write_text_atomic(config_path, yaml.safe_dump(config))
        writer = BioCypher(
            biocypher_config_path=str(config_path),
            schema_config_path=str(schema_path),
            output_directory=str(directory / "biocypher"),
        )

        def properties(value: object) -> dict[str, object]:
            # BioCypher 0.9.7 _BatchWriter._write_node_data / _write_single_edge_list_to_file
            # quote scalars without escaping. Neo4j _write_array_string calls _quote_string
            # and already escapes list items. Escape only scalars; the round-trip test
            # must pass before changing the pinned writer version.
            return {
                key: val.replace('"', '""') if isinstance(val, str) else val
                for key in context.schema[concept_id(type(value))]["properties"]
                for val in (getattr(value, key),)
            }

        # BioCypher 0.9.7 leaves these iterable parameters unannotated. Keep the
        # exception local to its API; our tuples and GraphWriter remain checked.
        if context.nodes and not writer.write_nodes(  # pyright: ignore[reportUnknownMemberType]
            (identity, concept_id(type(row.value)), properties(row.value))
            for identity, row in sorted(context.nodes.items())
        ):
            raise ValueError("BioCypher node export failed")
        if context.edges and not writer.write_edges(  # pyright: ignore[reportUnknownMemberType]
            (
                identity,
                getattr(row.value, "source"),
                getattr(row.value, "target"),
                concept_id(type(row.value)),
                properties(row.value),
            )
            for identity, row in sorted(context.edges.items())
        ):
            raise ValueError("BioCypher edge export failed")
        if context.nodes or context.edges:
            writer.write_import_call()
        with (directory / "provenance.jsonl").open("w", encoding="utf-8") as output:
            for kind, records in (("node", context.nodes), ("edge", context.edges)):
                for identity, row in sorted(records.items()):
                    output.write(
                        json.dumps(
                            {
                                "kind": kind,
                                "id": identity,
                                "concept": concept_id(type(row.value)),
                                "mappings": sorted(row.mappings),
                                "evidence": [asdict(e) for e in sorted(row.evidence)],
                            },
                            sort_keys=True,
                        )
                        + "\n"
                    )
        return [str(path.relative_to(directory)) for path in sorted(directory.rglob("*")) if path.is_file()]
