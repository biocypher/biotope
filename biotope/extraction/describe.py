from __future__ import annotations

from typing import Any, cast

from biotope.extraction.schema import Schema


CROISSANT_TYPES = {"string": "sc:Text", "integer": "sc:Integer", "number": "sc:Float", "boolean": "sc:Boolean"}
EVIDENCE = (
    ("quote", "The text the extractor quoted for the value."),
    ("locator", "Where the extractor found the value, in that extractor's notation, such as a page or a row."),
)


def describe(metadata: dict[str, Any], schema: Schema, file_id: str, name: str, records: list[dict[str, Any]]) -> None:
    def column(
        path: str,
        description: str,
        data_type: str | None = None,
        *,
        nullable: bool = True,
        many: bool = False,
        children: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        item: dict[str, Any] = {
            "@type": "cr:Field",
            "@id": f"{name}/{path}",
            "name": path.rsplit("/", 1)[-1],
            "description": description,
            "source": {"fileObject": {"@id": file_id}, "extract": {"column": path}},
        }
        if data_type:
            item["dataType"] = data_type
        if many:
            item["cr:isArray"] = True
        if not nullable:
            item["biotope:nullable"] = False
        if children:
            item["subField"] = children
        return item

    def evidenced(path: str, entry_description: str, data_type: str, nullable: bool, many: bool) -> dict[str, Any]:
        evidence = [column(f"{path}/evidence/{key}", text, "sc:Text") for key, text in EVIDENCE]
        return column(
            path,
            f"{entry_description} With its evidence.",
            nullable=False,
            many=many,
            children=[
                column(f"{path}/value", entry_description, data_type, nullable=nullable),
                column(
                    f"{path}/evidence",
                    "The value's evidence; null when the extractor gave neither a quote nor a locator.",
                    children=evidence,
                ),
            ],
        )

    values = [
        evidenced(
            f"values/{entry.name}",
            entry.description or entry.name,
            CROISSANT_TYPES[entry.type],
            entry.nullable,
            entry.many,
        )
        for entry in schema.fields
    ]
    kinds: dict[str, set[str | None]] = {}
    for record in records:
        for key, value in cast(dict[str, Any], record["provenance"]["extractor"]["settings"]).items():
            if value is not None:
                kinds.setdefault(key, set()).add(_croissant_type(value))
    settings = {key: kind for key, found in kinds.items() if (kind := _common_type(found))}
    extractor = [
        column("provenance/extractor/name", "The extractor's name.", "sc:Text", nullable=False),
        column("provenance/extractor/version", "The extractor's version.", "sc:Text", nullable=False),
    ]
    if settings:
        extractor.append(
            column(
                "provenance/extractor/settings",
                "The extractor's settings that shape its output, such as the model.",
                nullable=False,
                children=[
                    column(f"provenance/extractor/settings/{key}", f"The extractor setting {key}.", kind)
                    for key, kind in sorted(settings.items())
                ],
            )
        )
    provenance = [
        column("provenance/document_sha256", "SHA-256 digest of the document file.", "sc:Text", nullable=False),
        column("provenance/schema", "The extraction schema's class name.", "sc:Text", nullable=False),
        column(
            "provenance/schema_revision",
            "Digest of the schema's name, description, record key and fields.",
            "sc:Text",
            nullable=False,
        ),
        column("provenance/extractor", "The extractor that produced the record.", nullable=False, children=extractor),
        column(
            "provenance/redone",
            "True when the document was extracted again on request although its inputs were unchanged.",
            "sc:Boolean",
        ),
    ]
    fields = [
        column(
            "id",
            "The record ID: the document's dataset folder and its path within it, then the record key's values.",
            "sc:Text",
            nullable=False,
        ),
        column("document", "The document's path in the project.", "sc:Text", nullable=False),
        column("values", f"{schema.name} values. {schema.description}".strip(), nullable=False, children=values),
        column("provenance", "How the record was extracted.", nullable=False, children=provenance),
    ]
    record_sets = cast(list[dict[str, Any]], metadata.setdefault("recordSet", []))
    record_set: dict[str, Any] | None = next((item for item in record_sets if item.get("@id") == name), None)
    if record_set is None:
        record_set = {"@type": "cr:RecordSet", "@id": name, "name": name}
        record_sets.append(record_set)
    record_set["description"] = f"{schema.name} records extracted from documents, one per line."
    record_set["key"] = {"@id": f"{name}/id"}
    record_set["field"] = fields


def _croissant_type(value: object) -> str | None:
    if isinstance(value, dict | list):
        return None
    if isinstance(value, bool):
        return "sc:Boolean"
    if isinstance(value, int):
        return "sc:Integer"
    return "sc:Float" if isinstance(value, float) else "sc:Text"


def _common_type(kinds: set[str | None]) -> str | None:
    if kinds == {"sc:Integer", "sc:Float"}:
        return "sc:Float"
    return next(iter(kinds)) if len(kinds) == 1 else None
