from __future__ import annotations

import json
from pathlib import Path

from biotope.graph.runtime import RunContext
from biotope.graph.sources import write_text_atomic


ENTITIES = "entities.json"


def write_entities(path: Path, context: RunContext) -> None:
    def block(name: str, items: list[dict[str, object]]) -> str:
        lines = ",\n".join(
            json.dumps(item, separators=(",", ":"), ensure_ascii=False, allow_nan=False) for item in items
        )
        return f"{json.dumps(name)}:[\n{lines}\n]" if items else f"{json.dumps(name)}:[]"

    header = '{"schema_version":1,"report_kind":"biotope.entities",\n'
    write_text_atomic(
        path, header + block("entities", context.entities) + ",\n" + block("relations", context.relations) + "\n}\n"
    )
