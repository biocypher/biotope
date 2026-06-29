"""DuckDB-backed acquisition context.

A generic, dataset-agnostic streamer over Croissant record sets. Reads
Parquet (Hive-partitioned or flat) and CSV files via DuckDB and yields
:class:`RecordRow` views that map field names → values.

This is the minimal port of ``open_targets.adapter.context.AcquisitionContext``
that drops the OT scan-operation predicate DSL. Filtering can be added by the
mapping layer through a simple ``where: str`` SQL fragment if needed.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb

from biotope.croissant.spec import (
    CroissantDatasetModel,
    CroissantFileObjectModel,
    CroissantFileSetModel,
    CroissantRecordSetModel,
)


@dataclass(frozen=True)
class RecordRow:
    """One row from a record set, keyed by field name."""

    record_set: str
    values: Mapping[str, Any]

    def __getitem__(self, field: str) -> Any:
        return self.values[field]

    def get(self, field: str, default: Any = None) -> Any:
        """Return the value for ``field`` or ``default`` if absent."""
        return self.values.get(field, default)


PARQUET_FORMATS = frozenset(
    {
        "application/x-parquet",
        "application/vnd.apache.parquet",
        "application/parquet",
    },
)
CSV_FORMATS = frozenset({"text/csv", "application/csv"})
TSV_FORMATS = frozenset({"text/tab-separated-values"})


class AcquisitionContext:
    """Stream records out of the file distributions described by a Croissant model.

    The context resolves each :class:`CroissantRecordSetModel` to a set of
    on-disk files using the dataset's distribution entries and a user-supplied
    ``datasets_location`` root (or the explicit ``contentUrl`` when set to a
    local path). Streaming is lazy: a generator per record set, materialising
    rows one at a time via DuckDB.
    """

    def __init__(
        self,
        dataset: CroissantDatasetModel,
        datasets_location: str | Path,
        *,
        limit: int | None = None,
    ) -> None:
        self.dataset = dataset
        self.datasets_location = Path(datasets_location)
        self.limit = limit
        self._conn = duckdb.connect(":memory:")

    def close(self) -> None:
        """Close the underlying DuckDB connection."""
        self._conn.close()

    def __enter__(self) -> AcquisitionContext:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def stream(
        self,
        record_set: str | CroissantRecordSetModel,
        *,
        fields: Sequence[str] | None = None,
        where: str | None = None,
    ) -> Iterator[RecordRow]:
        """Yield :class:`RecordRow` instances for ``record_set``.

        ``fields`` selects a subset of columns; ``None`` selects all top-level
        fields declared in the record set. ``where`` is an optional raw SQL
        predicate applied to the relation.
        """
        rs = self._resolve_record_set(record_set)
        path = self._resolve_path(rs)
        relation = self._read(path)

        selected = list(fields) if fields is not None else [f.name for f in rs.field]
        relation = relation.select(*[_quote_ident(f) for f in selected])
        if where is not None:
            relation = relation.filter(where)
        if self.limit is not None:
            relation = relation.limit(self.limit)

        while True:
            row = relation.fetchone()
            if row is None:
                break
            yield RecordRow(record_set=rs.name, values=dict(zip(selected, row, strict=False)))

    def datasets(self) -> Iterable[CroissantRecordSetModel]:
        """Iterate over the record sets in the wrapped dataset."""
        return list(self.dataset.record_set)

    def _resolve_record_set(self, record_set: str | CroissantRecordSetModel) -> CroissantRecordSetModel:
        if isinstance(record_set, CroissantRecordSetModel):
            return record_set
        rs = self.dataset.record_set_by_name(record_set)
        if rs is None:
            msg = f"Record set {record_set!r} not found in dataset"
            raise KeyError(msg)
        return rs

    def _resolve_path(self, rs: CroissantRecordSetModel) -> Path:
        """Resolve a record set to a filesystem glob path.

        Strategy, in order:

        1. Follow ``rs.field[*].source.fileSet`` / ``fileObject`` to the
           referenced distribution entry (canonical Croissant link).
        2. Match a FileSet/FileObject by ``dist.id == rs.name`` or
           ``dist.id == f"{rs.name}-fileset"`` (baker convention).
        3. Default to ``datasets_location / record_set.name`` and let DuckDB
           glob with a recursive ``**/*`` pattern.
        """
        dist_by_id: dict[str, CroissantFileSetModel | CroissantFileObjectModel] = {
            d.id: d for d in self.dataset.distribution if d.id
        }

        # 1. Field source links (canonical).
        for field in rs.field:
            if field.source is None:
                continue
            fs_id = field.source.file_set_id
            if fs_id and fs_id in dist_by_id:
                dist = dist_by_id[fs_id]
                if isinstance(dist, CroissantFileSetModel):
                    return self.datasets_location / dist.includes
                if isinstance(dist, CroissantFileObjectModel) and dist.content_url:
                    return self.datasets_location / dist.content_url
            fo_id = field.source.file_object_id
            if fo_id and fo_id in dist_by_id:
                dist = dist_by_id[fo_id]
                if isinstance(dist, CroissantFileObjectModel) and dist.content_url:
                    return self.datasets_location / dist.content_url
                if isinstance(dist, CroissantFileSetModel):
                    return self.datasets_location / dist.includes

        # 2. Heuristic id matching.
        for candidate_id in (rs.name, f"{rs.name}-fileset"):
            dist = dist_by_id.get(candidate_id)
            if isinstance(dist, CroissantFileSetModel):
                return self.datasets_location / dist.includes
            if isinstance(dist, CroissantFileObjectModel):
                if dist.content_url is None:
                    msg = f"FileObject {dist.id!r} has no contentUrl"
                    raise ValueError(msg)
                return self.datasets_location / dist.content_url

        # 3. Fallback.
        return self.datasets_location / rs.name

    def _read(self, path: Path) -> duckdb.DuckDBPyRelation:
        """Read a file or directory via DuckDB, inferring format from extension."""
        suffix = path.suffix.lower() or self._guess_extension(path)
        path_str = str(path)
        if suffix in {".parquet", ".pq"}:
            return self._conn.read_parquet(path_str, hive_partitioning=True)
        if suffix in {".csv", ".tsv"}:
            sep = "\t" if suffix == ".tsv" else ","
            # all_varchar=True disables DuckDB column type auto-detection, which
            # samples only the first N rows and mis-types columns whose string
            # values appear later (e.g. cell_type read as BIGINT then hitting
            # "B_cell"). The graph build stringifies every value anyway and no
            # mapping uses numeric `where` filters, so VARCHAR-everywhere is safe.
            return self._conn.read_csv(path_str, header=True, sep=sep, all_varchar=True)
        if suffix in {".json", ".jsonl", ".ndjson"}:
            return self._conn.read_json(path_str)
        # Fallback: assume parquet directory.
        return self._conn.read_parquet(f"{path_str}/**/*.parquet", hive_partitioning=True)

    @staticmethod
    def _guess_extension(path: Path) -> str:
        for child in path.glob("*"):
            if child.is_file():
                return child.suffix.lower()
        return ""


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'
