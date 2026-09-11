"""Narrow BioCypher integration: local Neo4j import files, without a database."""

from __future__ import annotations

import importlib.metadata
import json
import logging
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict
from pathlib import Path
from typing import Any, Protocol, cast

import yaml

from biotope.graph.context import CONTEXT_CONCEPT, CONTEXT_LABEL, CONTEXT_PROPERTIES, context_rows
from biotope.graph.runtime import RunContext
from biotope.graph.sources import digest, write_text_atomic
from biotope.graph.topology import concept_id


SUPPORTED_BIOCYPHER = ((0, 17), (0, 18))
"""Lowest tested BioCypher release, and the first release above the tested range.

BioCypher is pre-1.0 and moves defaults between minors: 0.17 flipped offline
Neo4j output to Parquet and renamed the CSV delimiter keys. The range therefore
spans patches, which fix behaviour, and stops at the next minor, which may
change it.
"""

EXPORT_FORMATS = {
    "csv": frozenset({".csv", ".sh"}),
    "parquet": frozenset({".parquet", ".sh"}),
}
"""Selectable data formats, and the file suffixes each is expected to produce.

CSV writes a header file beside each data file; Parquet carries its schema
inline and writes neither. Parquet needs a Neo4j release whose import accepts
it, so the choice belongs to whoever runs the import rather than to a library
default.
"""

ARRAY_DELIMITER = ";"
"""Separator inside an exported string list, matching neo4j-admin's own default."""


def supported_specifier() -> str:
    """Render the tested range as a requirement specifier."""
    low, high = SUPPORTED_BIOCYPHER
    return f">={'.'.join(map(str, low))},<{'.'.join(map(str, high))}"


def _release(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", version.partition("+")[0])[:3])


def _format_name(file_format: str) -> str:
    return f"neo4j-admin-{file_format}"


class GraphWriter(Protocol):
    """An output boundary independent of project source loaders and mappings."""

    def check_environment(self) -> dict[str, object]:
        """Verify the exporter this environment will actually use, before any data is read.

        A build that discovers an unsupported writer after loading its sources
        wastes the run and can still produce files in an untested format.
        """
        ...

    def write(self, context: RunContext, directory: Path, *, query_context: dict[str, Any]) -> list[str]:
        """Write validated graph data with its interpretation context; return artifact paths."""
        ...


def export_labels(concepts: Iterable[str]) -> dict[str, str]:
    # Use readable PascalCase from the complete namespaced ID. Disambiguate only
    # normalization collisions, including the writer's synthetic Entity root.
    bases = {
        semantic: "".join(word.capitalize() for word in re.findall(r"[a-z0-9]+", semantic.lower()))
        for semantic in concepts
    }
    bases = {semantic: base if base and base[0].isalpha() else "Concept" + base for semantic, base in bases.items()}
    counts = Counter(bases.values())
    reserved = {"Entity", CONTEXT_LABEL}
    labels = {
        semantic: base + "H" + digest(semantic)[:10] if counts[base] > 1 or base in reserved else base
        for semantic, base in bases.items()
    }
    if len(set(labels.values())) != len(labels):
        raise ValueError("Graph concept IDs collide after export label normalization; use distinct semantic IDs")
    return labels


class BioCypherWriter:
    """Derive a local schema/ontology and write one offline BioCypher format."""

    def __init__(self, file_format: str = "csv") -> None:
        if file_format not in EXPORT_FORMATS:
            raise ValueError(f"Unsupported export format {file_format!r}; choose one of {sorted(EXPORT_FORMATS)}.")
        self.file_format = file_format

    def check_environment(self) -> dict[str, object]:
        """Refuse an untested writer before the pipeline reads a single source byte.

        Escaping, file naming and the physical format are properties of one
        writer release, not of the BioCypher API. A different version can
        succeed and still write something this package has never round-tripped.
        """
        specifier = supported_specifier()
        contract = _format_name(self.file_format)
        try:
            installed = importlib.metadata.version("biocypher")
        except importlib.metadata.PackageNotFoundError as exc:
            raise ValueError(
                "BioCypher is not installed in this environment. Install a supported writer with "
                f"`pip install 'biocypher{specifier}'`, or install biotope[graph]."
            ) from exc
        low, high = SUPPORTED_BIOCYPHER
        if not low <= _release(installed) < high:
            raise ValueError(
                f"biotope exports through BioCypher {specifier}, the range its {contract} "
                f"quoting and layout are tested against; this environment has {installed}. "
                f"Install a supported writer with `pip install 'biocypher{specifier}'`, or pass a "
                "GraphWriter for the version you need and test its output format yourself."
            )
        return {"exporter": "biocypher", "version": installed, "format": contract}

    def write(self, context: RunContext, directory: Path, *, query_context: dict[str, Any]) -> list[str]:
        """Write Neo4j import files, the query context and an identity-keyed provenance sidecar."""
        environment = self.check_environment()
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
                    any(char in item for char in ARRAY_DELIMITER + "\r\n") for item in cast(list[str], value)
                ):
                    raise ValueError(f"Unsupported BioCypher string-list separator/newline in {identity}.{name}")
        labels = export_labels(context.schema)
        rows = context_rows(query_context)
        schema = {
            labels[semantic]: {
                "represented_as": item["kind"],
                "input_label": semantic,
                "is_a": "entity",
                "properties": item["properties"],
            }
            for semantic, item in context.schema.items()
        }
        schema[CONTEXT_LABEL] = {
            "represented_as": "node",
            "input_label": CONTEXT_CONCEPT,
            "is_a": "entity",
            "properties": dict(CONTEXT_PROPERTIES),
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
            json.dumps(
                {
                    "concepts": context.schema,
                    "export_labels": {**labels, CONTEXT_CONCEPT: CONTEXT_LABEL},
                    "exporter": environment,
                },
                indent=2,
            )
            + "\n",
        )
        write_text_atomic(
            directory / "query_context.json",
            json.dumps(query_context, indent=2, sort_keys=True, allow_nan=False) + "\n",
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
                "file_format": self.file_format,
                "csv_column_delimiter": ",",
                "csv_array_delimiter": ARRAY_DELIMITER,
                "csv_string_quote_character": '"',
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
            return {key: getattr(value, key) for key in context.schema[concept_id(type(value))]["properties"]}

        # BioCypher 0.9.7 leaves these iterable parameters unannotated. Keep the
        # exception local to its API; our tuples and GraphWriter remain checked.
        if not writer.write_nodes(  # pyright: ignore[reportUnknownMemberType]
            [
                *(
                    (identity, concept_id(type(row.value)), properties(row.value))
                    for identity, row in sorted(context.nodes.items())
                ),
                *((identity, CONTEXT_CONCEPT, dict(row)) for identity, row in rows),
            ]
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
        writer.write_import_call()
        unexpected = sorted(
            str(path.relative_to(directory))
            for path in (directory / "biocypher").rglob("*")
            if path.is_file() and path.suffix not in EXPORT_FORMATS[self.file_format]
        )
        if unexpected:
            raise ValueError(
                f"BioCypher wrote files the declared {_format_name(self.file_format)} contract does "
                f"not cover: {', '.join(unexpected)}. The writer and the declaration disagree; "
                "reconcile them before accepting the output."
            )
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
