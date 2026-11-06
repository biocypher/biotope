from __future__ import annotations

from typing import Any, cast

from biotope.extraction.schema import Schema


CROISSANT_TYPES = {"string": "sc:Text", "integer": "sc:Integer", "number": "sc:Float", "boolean": "sc:Boolean"}


def describe(metadata: dict[str, Any], schema: Schema, file_id: str, name: str, origin: dict[str, Any]) -> None:
    def column(
        field: str, path: str, description: str, data_type: str, *, nullable: bool = False, many: bool = False
    ) -> dict[str, Any]:
        item: dict[str, Any] = {
            "@type": "cr:Field",
            "@id": f"{name}/{field}",
            "name": field,
            "description": description,
            "dataType": data_type,
            "source": {"fileObject": {"@id": file_id}, "extract": {"column": path}},
        }
        if many:
            item["cr:isArray"] = True
        if not nullable:
            item["biotope:nullable"] = False
        return item

    fields = [
        column(
            "id",
            "id",
            "The record ID: the document's dataset folder and its path within it, then the record key's values.",
            "sc:Text",
        ),
        column("document", "document", "The document's path in the project.", "sc:Text"),
        *(
            column(
                entry.name,
                f"values/{entry.name}/value",
                entry.description or entry.name,
                CROISSANT_TYPES[entry.type],
                nullable=entry.nullable,
                many=entry.many,
            )
            for entry in schema.fields
        ),
    ]
    record_sets = cast(list[dict[str, Any]], metadata.setdefault("recordSet", []))
    record_set: dict[str, Any] | None = next((item for item in record_sets if item.get("@id") == name), None)
    if record_set is None:
        record_set = {"@type": "cr:RecordSet", "@id": name, "name": name}
        record_sets.append(record_set)
    record_set["description"] = f"{schema.name} records extracted from documents. {schema.description}".strip()
    record_set["key"] = {"@id": f"{name}/id"}
    record_set["field"] = fields
    entries = cast(list[dict[str, Any]], metadata["distribution"])
    next(entry for entry in entries if entry.get("@id") == file_id).update(origin)
