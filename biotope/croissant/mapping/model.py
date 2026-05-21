"""Semantic mapping IR for ``mapping.yaml`` (v1 entities/relations).

Top-level shape::

    croissant: ./datasets/open-targets.croissant.json
    ids:
      target_curie:
        field: ensembl_id
        transform: as_curie
        args: { prefix: ensembl }
    entities:
      target:
        record_set: targets
        scan: row
        schema_term: Target
        namespace: ensembl
        id: { use: target_curie }
        properties:
          symbol: { field: approved_symbol }
          biotype: biotype
    relations:
      target_associated_with_disease:
        record_set: target_disease
        scan: { explode: associated_diseases }
        source: { entity: target, use: target_curie }
        target:
          entity: disease
          field: "$item.disease_id"
          transform: as_curie
          args: { prefix: mondo }
        properties:
          score: score

A ``Mapping`` accepts partially-resolved input (slots may omit ``record_set``,
``id``, etc.) so the wizard can autosave between steps. The strict build path
calls :meth:`Mapping.assert_resolved` to refuse compilation of partial inputs.

Legacy ``nodes``/``edges`` mappings are explicitly rejected by the loader with
a clear regeneration message — there is no automated migration in v1.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# ---------------------------------------------------------------------------
# Selectors
# ---------------------------------------------------------------------------


class Selector(_Model):
    """How to derive a value from a row.

    A selector resolves a value from either a record field (``field``) or a
    named reusable selector (``use``), optionally passing it through a named
    transform.

    YAML accepts two forms — both normalize to this model:

    * String shorthand: ``symbol`` → ``{field: symbol}``
    * Full form: ``{field: ensembl_id, transform: as_curie, args: {prefix: ensembl}}``
    """

    field: str | None = None
    use: str | None = None
    transform: str = "passthrough"
    args: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        if isinstance(data, str):
            return {"field": data}
        return data

    @model_validator(mode="after")
    def _check(self) -> Selector:
        if self.field is not None and self.use is not None:
            msg = "Selector cannot set both `field` and `use`"
            raise ValueError(msg)
        return self

    def is_resolved(self) -> bool:
        if self.transform == "hash_id":
            return bool(self.args.get("fields"))
        return self.field is not None or self.use is not None


class Endpoint(_Model):
    """A relation endpoint: a selector plus the entity it references.

    ``entity`` names the local entity key in this mapping that the endpoint
    refers to. It is validated at load against the entity table.
    """

    entity: str | None = None
    field: str | None = None
    use: str | None = None
    transform: str = "passthrough"
    args: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check(self) -> Endpoint:
        if self.field is not None and self.use is not None:
            msg = "Endpoint cannot set both `field` and `use`"
            raise ValueError(msg)
        return self

    def is_resolved(self) -> bool:
        return self.entity is not None and (self.field is not None or self.use is not None)

    def as_selector(self) -> Selector:
        return Selector(field=self.field, use=self.use, transform=self.transform, args=self.args)


# ---------------------------------------------------------------------------
# Scans
# ---------------------------------------------------------------------------


class RowScan(_Model):
    """Mark a scan as `row` — yield each base record."""

    kind: Literal["row"] = "row"


class ExplodeScan(_Model):
    """Yield one record per element (or Cartesian-product combination) of array-typed fields.

    Single-field form (string): the field's elements are projected under the
    default axis name ``item``; selectors reference them as ``$item`` (or
    ``$item.<subfield>`` when the array is of structs).

    Multi-field form (dict): each axis ``<name>: <field>`` becomes accessible
    via ``$<name>``; the runtime yields one context per element of the
    Cartesian product across all axes.
    """

    axes: dict[str, str]

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        if isinstance(data, dict) and "explode" in data:
            explode = data["explode"]
            if isinstance(explode, str):
                return {"axes": {"item": explode}}
            if isinstance(explode, dict):
                # axis_name -> field_name
                if not explode:
                    msg = "scan.explode dict must not be empty"
                    raise ValueError(msg)
                for axis_name, field_name in explode.items():
                    if not _is_axis_name(axis_name):
                        raise ValueError(
                            f"scan.explode axis name {axis_name!r} must be snake_case "
                            "(no leading $; reserved name `row` cannot be reused)"
                        )
                    if not isinstance(field_name, str):
                        raise ValueError(
                            f"scan.explode.{axis_name} must map to a field name (str), "
                            f"got {type(field_name).__name__}"
                        )
                return {"axes": dict(explode)}
            raise ValueError(
                f"scan.explode must be a field name or a {{axis: field, ...}} dict; "
                f"got {type(explode).__name__}"
            )
        return data

    @property
    def explode(self) -> str | dict[str, str]:
        """YAML-side projection: a string for single-axis, a dict for multi-axis."""
        if list(self.axes.keys()) == ["item"]:
            return self.axes["item"]
        return dict(self.axes)


Scan = RowScan | ExplodeScan


def _is_axis_name(name: str) -> bool:
    if name == "row":
        return False
    return bool(_SNAKE_RE.match(name))


def _coerce_scan(value: Any) -> Scan:
    if value is None or value == "row":
        return RowScan()
    if isinstance(value, RowScan | ExplodeScan):
        return value
    if isinstance(value, dict):
        if "explode" in value:
            return ExplodeScan.model_validate(value)
        if value == {} or value.get("kind") == "row":
            return RowScan()
    msg = f"Unsupported scan {value!r}; expected 'row' or {{explode: <field-or-dict>}}"
    raise ValueError(msg)


# ---------------------------------------------------------------------------
# Entities and Relations
# ---------------------------------------------------------------------------


class EntityMapping(_Model):
    """One semantic entity declaration (compiles to a BioCypher node type)."""

    record_set: str | None = None
    scan: Scan = Field(default_factory=RowScan)
    schema_term: str | None = None
    namespace: str | None = None
    id: Selector | None = None
    properties: dict[str, Selector] = Field(default_factory=dict)
    where: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        if "scan" in data:
            data["scan"] = _coerce_scan(data["scan"])
        if "properties" in data and isinstance(data["properties"], dict):
            data["properties"] = {k: _coerce_selector_field(v) for k, v in data["properties"].items()}
        return data

    def is_resolved(self) -> bool:
        return self.record_set is not None and self.id is not None and self.id.is_resolved()


class RelationMapping(_Model):
    """One semantic relation declaration (compiles to a BioCypher edge type)."""

    record_set: str | None = None
    scan: Scan = Field(default_factory=RowScan)
    schema_term: str | None = None
    source: Endpoint | None = None
    target: Endpoint | None = None
    properties: dict[str, Selector] = Field(default_factory=dict)
    where: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        if "scan" in data:
            data["scan"] = _coerce_scan(data["scan"])
        if "properties" in data and isinstance(data["properties"], dict):
            data["properties"] = {k: _coerce_selector_field(v) for k, v in data["properties"].items()}
        return data

    def is_resolved(self) -> bool:
        return (
            self.record_set is not None
            and self.source is not None
            and self.source.is_resolved()
            and self.target is not None
            and self.target.is_resolved()
        )


def _coerce_selector_field(value: Any) -> Any:
    """Normalize a property value: string shorthand → ``{field: <value>}``."""
    if isinstance(value, str):
        return {"field": value}
    return value


# ---------------------------------------------------------------------------
# Top-level Mapping
# ---------------------------------------------------------------------------


_LEGACY_KEYS = ("nodes", "edges")
_LEGACY_MESSAGE = (
    "Legacy `nodes`/`edges` mapping is no longer supported. "
    "Regenerate via `biotope map scaffold <croissant>` and resolve slots with `biotope map`."
)


class Mapping(_Model):
    """Top-level ``mapping.yaml``."""

    croissant: str
    ids: dict[str, Selector] = Field(default_factory=dict)
    entities: dict[str, EntityMapping] = Field(default_factory=dict)
    relations: dict[str, RelationMapping] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _reject_legacy(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for key in _LEGACY_KEYS:
                if key in data:
                    raise ValueError(_LEGACY_MESSAGE)
        return data

    @model_validator(mode="after")
    def _validate_keys_and_refs(self) -> Mapping:
        for name in list(self.entities) + list(self.relations) + list(self.ids):
            if not _is_snake_case(name):
                msg = f"Mapping keys must be snake_case; got {name!r}"
                raise ValueError(msg)

        for rel_name, relation in self.relations.items():
            for side_name, side in (("source", relation.source), ("target", relation.target)):
                if side is None or side.entity is None:
                    continue
                if side.entity not in self.entities:
                    msg = (
                        f"Relation {rel_name!r} {side_name} references unknown entity "
                        f"{side.entity!r}; known entities: {sorted(self.entities)}"
                    )
                    raise ValueError(msg)

        for entity_name, entity in self.entities.items():
            self._check_selector_use(f"entities.{entity_name}.id", entity.id)
            for prop_name, prop in entity.properties.items():
                self._check_selector_use(f"entities.{entity_name}.properties.{prop_name}", prop)
            self._check_item_placement(
                entity.scan,
                f"entities.{entity_name}",
                entity.id,
                entity.properties.values(),
                where=entity.where,
            )

        for rel_name, relation in self.relations.items():
            if relation.source is not None:
                self._check_selector_use(
                    f"relations.{rel_name}.source",
                    relation.source.as_selector(),
                )
            if relation.target is not None:
                self._check_selector_use(
                    f"relations.{rel_name}.target",
                    relation.target.as_selector(),
                )
            for prop_name, prop in relation.properties.items():
                self._check_selector_use(f"relations.{rel_name}.properties.{prop_name}", prop)
            selectors = []
            if relation.source is not None:
                selectors.append(relation.source.as_selector())
            if relation.target is not None:
                selectors.append(relation.target.as_selector())
            selectors.extend(relation.properties.values())
            self._check_item_placement(
                relation.scan,
                f"relations.{rel_name}",
                None,
                selectors,
                where=relation.where,
            )

        return self

    def _check_selector_use(self, path: str, selector: Selector | None) -> None:
        if selector is None or selector.use is None:
            return
        if selector.use not in self.ids:
            msg = (
                f"{path}: `use: {selector.use!r}` refers to an unknown id; "
                f"known ids: {sorted(self.ids)}"
            )
            raise ValueError(msg)

    def _check_item_placement(
        self,
        scan: Scan,
        path: str,
        primary: Selector | None,
        others: Any,
        where: str | None,
    ) -> None:
        if where is not None and "$" in where:
            # Any explode-axis reference is invalid in `where` — `where` runs on the
            # base row before explode.
            if "$item" in where:
                raise ValueError(f"{path}.where: `$item` is not valid inside `where`")
            for token in re.findall(r"\$[a-z][a-z0-9_]*", where):
                raise ValueError(
                    f"{path}.where: explode-axis reference {token!r} is not valid inside `where` "
                    "(where runs on the base row before explode)"
                )
        axes = scan.axes if isinstance(scan, ExplodeScan) else {}
        candidates: list[Selector] = []
        if primary is not None:
            candidates.append(primary)
        candidates.extend(others)
        for sel in candidates:
            if sel.field is None or not sel.field.startswith("$"):
                continue
            axis = _axis_name_from_field(sel.field)
            if not axes:
                raise ValueError(
                    f"{path}: `${axis}` selectors are only valid when `scan: explode`; "
                    f"got `field: {sel.field!r}` with `scan: row`"
                )
            if axis not in axes:
                raise ValueError(
                    f"{path}: `${axis}` is not an axis of this scan; "
                    f"declared axes: {sorted(axes)}"
                )

    # --- resolution helpers ---------------------------------------------------

    def is_resolved(self) -> bool:
        return not self.unresolved_slots()

    def unresolved_slots(self) -> list[str]:
        slots: list[str] = []
        for entity_name, entity in self.entities.items():
            if not entity.is_resolved():
                slots.append(f"entities.{entity_name}")
        for rel_name, relation in self.relations.items():
            if not relation.is_resolved():
                slots.append(f"relations.{rel_name}")
        return slots

    def assert_resolved(self) -> None:
        unresolved = self.unresolved_slots()
        if unresolved:
            joined = ", ".join(unresolved)
            msg = (
                f"Mapping has unresolved slots: {joined}. "
                f"Complete them with `biotope map` before running `biotope build`."
            )
            raise ValueError(msg)


_SNAKE_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def _is_snake_case(name: str) -> bool:
    return bool(_SNAKE_RE.match(name))


def _axis_name_from_field(field: str) -> str:
    """Extract the axis name from a `$<axis>` or `$<axis>.<sub>` selector field."""
    body = field[1:].split(".", 1)[0]
    return body


def to_snake_case(text: str) -> str:
    """Mechanical normalization of user-declared names to snake_case keys."""
    s = re.sub(r"[^0-9a-zA-Z]+", "_", text).strip("_").lower()
    if not s:
        msg = f"Cannot derive snake_case key from {text!r}"
        raise ValueError(msg)
    if s[0].isdigit():
        s = "_" + s
    return s


def to_sentence_case(snake: str) -> str:
    """Convert a snake_case mapping key to its lower-sentence-case schema term default."""
    return snake.replace("_", " ")
