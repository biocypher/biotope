"""Heuristic default mapping for a Croissant dataset.

Used when the user (or an agent) has not yet authored a ``mapping.yaml``. The
heuristic is intentionally trivial so the produced graph is obviously a
"first cut" inviting refinement:

* Each record set becomes a node type named after the record set.
* The first field whose name ends in ``id``/``_id`` becomes the node id;
  if none exists, a stable :func:`hash_id` over all scalar fields is used.
* Foreign-key-shaped fields — non-id fields whose name ends in ``_id`` and
  matches another record set's id — generate edges named
  ``<record_set>_to_<target_record_set>``.
"""

from __future__ import annotations

from biotope.croissant.spec import CroissantDatasetModel, FieldKind
from biotope.croissant.mapping.model import EdgeMapping, EndpointMapping, IdMapping, Mapping, NodeMapping


def _pick_id_field(record_set_fields: list[str]) -> str | None:
    for name in record_set_fields:
        lname = name.lower()
        if lname == "id" or lname.endswith("_id"):
            return name
    return None


def _scalar_field_names(record_set_fields: list[tuple[str, FieldKind]]) -> list[str]:
    return [n for n, k in record_set_fields if k not in (FieldKind.ARRAY, FieldKind.STRUCT)]


def default_mapping(dataset: CroissantDatasetModel, croissant_path: str) -> Mapping:
    """Return a :class:`Mapping` for ``dataset`` using simple heuristics."""
    record_set_id_field: dict[str, str | None] = {}
    record_set_fields: dict[str, list[tuple[str, FieldKind]]] = {}

    for rs in dataset.record_set:
        rs_fields = [(f.name, f.kind()) for f in rs.field]
        scalar_names = _scalar_field_names(rs_fields)
        record_set_fields[rs.name] = rs_fields
        record_set_id_field[rs.name] = _pick_id_field(scalar_names)

    nodes: list[NodeMapping] = []
    edges: list[EdgeMapping] = []

    for rs in dataset.record_set:
        rs_fields = record_set_fields[rs.name]
        scalar_names = _scalar_field_names(rs_fields)
        id_field = record_set_id_field[rs.name]

        if id_field is not None:
            id_mapping = IdMapping(**{"from": id_field})
        else:
            id_mapping = IdMapping(
                **{"from": scalar_names[0] if scalar_names else rs.name},
                transform="hash_id",
                args={"fields": scalar_names, "prefix": rs.name},
            )

        properties = [n for n in scalar_names if n != id_field]
        nodes.append(
            NodeMapping(
                record_set=rs.name,
                type=rs.name,
                id=id_mapping,
                properties=properties,
            ),
        )

        for field_name in scalar_names:
            if field_name == id_field:
                continue
            for other_rs, other_id in record_set_id_field.items():
                if other_rs == rs.name or other_id is None:
                    continue
                # FK heuristic: <other_rs_singular>_id ≈ other_rs name.
                if field_name.endswith("_id") and field_name[:-3].lower() in other_rs.lower():
                    edges.append(
                        EdgeMapping(
                            record_set=rs.name,
                            type=f"{rs.name}_to_{other_rs}",
                            source=EndpointMapping(**{"from": id_field}) if id_field else
                            EndpointMapping(**{"from": scalar_names[0]}),
                            target=EndpointMapping(**{"from": field_name}),
                        ),
                    )

    return Mapping(croissant=croissant_path, nodes=nodes, edges=edges)
