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
from dataclasses import dataclass
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
            yield ResolutionContext(row=row, item=None, ids=ids)


@dataclass
class ExplodeScanOperation:
    """Yield one context per element of ``array_field`` on each base row.

    Non-list values for ``array_field`` are skipped (the row contributes
    nothing rather than raising). ``None`` and empty arrays also yield nothing.
    """

    record_set: str
    array_field: str
    fields: list[str] | None = None
    where: str | None = None

    def iter_contexts(
        self,
        context: AcquisitionContext,
        *,
        ids: dict | None = None,
    ) -> Iterator[ResolutionContext]:
        fields = self.fields
        if fields is not None and self.array_field not in fields:
            fields = [*fields, self.array_field]
        for row in context.stream(self.record_set, fields=fields, where=self.where):
            elements = row.get(self.array_field)
            if elements is None:
                continue
            if not isinstance(elements, list | tuple):
                continue
            for element in elements:
                yield ResolutionContext(row=row, item=element, ids=ids)


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
            array_field=scan.explode,
            fields=fields,
            where=where,
        )
    msg = f"Unsupported scan {scan!r}"
    raise TypeError(msg)
