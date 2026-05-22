"""Scan operations: how a mapping iterates a record set into evaluation contexts.

Two built-in scans cover v1:

* :class:`RowScanOperation` — one :class:`ResolutionContext` per row.
* :class:`ExplodeScanOperation` — given an array-valued field, yields one
  context per element of the array on each row. The element is exposed to
  selectors as ``$item`` and can be sub-pathed (``$item.foo``).

The registry below is the only public extension seam, but only the two
built-ins are exposed in v1.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from itertools import product
from typing import TYPE_CHECKING

from biotope.croissant.mapping.model import ExplodeScan, RowScan, Scan
from biotope.croissant.mapping.selectors import ResolutionContext


if TYPE_CHECKING:
    from biotope.croissant.acquisition.context import AcquisitionContext


@dataclass
class RowScanOperation:
    """Yield one :class:`ResolutionContext` per base row."""

    record_set: str
    fields: list[str] | None = None
    where: str | None = None

    def iter_contexts(
        self,
        context: AcquisitionContext,
        *,
        ids: dict | None = None,
    ) -> Iterator[ResolutionContext]:
        for row in context.stream(self.record_set, fields=self.fields, where=self.where):
            yield ResolutionContext(row=row, items=None, ids=ids)


@dataclass
class ExplodeScanOperation:
    """Yield one context per element of the Cartesian product across explode axes.

    ``axes`` maps axis name → array field name. Non-list, ``None``, or empty
    array values cause that row to contribute nothing (the cross product with
    an empty axis is empty).
    """

    record_set: str
    axes: dict[str, str] = field(default_factory=dict)
    fields: list[str] | None = None
    where: str | None = None

    def iter_contexts(
        self,
        context: AcquisitionContext,
        *,
        ids: dict | None = None,
    ) -> Iterator[ResolutionContext]:
        projection = list(self.fields) if self.fields is not None else None
        if projection is not None:
            for array_field in self.axes.values():
                if array_field not in projection:
                    projection.append(array_field)
        for row in context.stream(self.record_set, fields=projection, where=self.where):
            arrays: list[list] = []
            names: list[str] = []
            row_is_empty = False
            for axis_name, array_field in self.axes.items():
                elements = row.get(array_field)
                if elements is None or not isinstance(elements, list | tuple):
                    row_is_empty = True
                    break
                arrays.append(list(elements))
                names.append(axis_name)
            if row_is_empty or not arrays:
                continue
            for combo in product(*arrays):
                yield ResolutionContext(
                    row=row,
                    items=dict(zip(names, combo, strict=False)),
                    ids=ids,
                )


def build_scan_operation(
    scan: Scan,
    *,
    record_set: str,
    fields: list[str] | None = None,
    where: str | None = None,
) -> RowScanOperation | ExplodeScanOperation:
    """Instantiate the runtime operation for a declared scan."""
    if isinstance(scan, RowScan):
        return RowScanOperation(record_set=record_set, fields=fields, where=where)
    if isinstance(scan, ExplodeScan):
        return ExplodeScanOperation(
            record_set=record_set,
            axes=dict(scan.axes),
            fields=fields,
            where=where,
        )
    msg = f"Unsupported scan {scan!r}"
    raise TypeError(msg)
