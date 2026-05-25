"""Typed Croissant 1.1 metadata models.

Ported and generalised from open-targets/open_targets/data/metadata/model.py.
This layer is the *only* one that touches raw Croissant JSON-LD. Every higher
layer consumes the typed model.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Literal
from urllib.request import urlopen

from pydantic import AliasChoices, BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class Key(str, Enum):
    """Reserved Croissant JSON-LD keys with leading ``@`` or special spelling."""

    ID = "@id"
    TYPE = "@type"
    CONTENT_URL = "contentUrl"
    RECORD_SET = "recordSet"


class CroissantScalarType(str, Enum):
    """Subset of ``sc:`` data types we recognise as scalars.

    Croissant inherits schema.org types; the spec defines a handful as canonical
    scalars and leaves everything else to extensions. The set below is the
    closed superset of what Open Targets, Croissant Baker, and the MLCommons
    examples emit in practice.
    """

    TEXT = "sc:Text"
    BOOLEAN = "sc:Boolean"
    INTEGER = "sc:Integer"
    FLOAT = "sc:Float"
    DATE = "sc:Date"
    URL = "sc:URL"


class FieldKind(str, Enum):
    """Normalised field shape derived from a Croissant field declaration."""

    BOOLEAN = "boolean"
    INTEGER = "integer"
    FLOAT = "float"
    STRING = "string"
    DATE = "date"
    URL = "url"
    ARRAY = "array"
    STRUCT = "struct"


SCALAR_KIND_MAP: dict[str, FieldKind] = {
    CroissantScalarType.TEXT.value: FieldKind.STRING,
    CroissantScalarType.BOOLEAN.value: FieldKind.BOOLEAN,
    CroissantScalarType.INTEGER.value: FieldKind.INTEGER,
    CroissantScalarType.FLOAT.value: FieldKind.FLOAT,
    CroissantScalarType.DATE.value: FieldKind.DATE,
    CroissantScalarType.URL.value: FieldKind.URL,
    # Croissant 1.0 extension types: typed integer / float precisions.
    # Precision is irrelevant for BioCypher mapping; collapse to INTEGER / FLOAT.
    "cr:Bool": FieldKind.BOOLEAN,
    "cr:Int8": FieldKind.INTEGER,
    "cr:Int16": FieldKind.INTEGER,
    "cr:Int32": FieldKind.INTEGER,
    "cr:Int64": FieldKind.INTEGER,
    "cr:UInt8": FieldKind.INTEGER,
    "cr:UInt16": FieldKind.INTEGER,
    "cr:UInt32": FieldKind.INTEGER,
    "cr:UInt64": FieldKind.INTEGER,
    "cr:Float16": FieldKind.FLOAT,
    "cr:Float32": FieldKind.FLOAT,
    "cr:Float64": FieldKind.FLOAT,
}


class ConfiguredBaseModel(BaseModel):
    """Base model with camelCase ↔ snake_case alias generation."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
        frozen=True,
    )


class CroissantFieldSource(ConfiguredBaseModel):
    """Field source link, e.g. ``{fileSet: {@id: target-fileset}, extract: ...}``."""

    file_object: dict | None = None
    file_set: dict | None = None
    extract: dict | None = None

    @property
    def file_set_id(self) -> str | None:
        if isinstance(self.file_set, dict):
            return self.file_set.get("@id")
        return None

    @property
    def file_object_id(self) -> str | None:
        if isinstance(self.file_object, dict):
            return self.file_object.get("@id")
        return None


class CroissantFieldModel(ConfiguredBaseModel):
    """A field within a Croissant record set."""

    name: str
    description: str | None = None
    data_type: str | None = None
    repeated: bool = Field(
        default=False,
        validation_alias=AliasChoices("repeated", "isArray", "cr:isArray"),
    )
    sub_field: list[CroissantFieldModel] = Field(default_factory=list)
    source: CroissantFieldSource | None = None

    def kind(self) -> FieldKind:
        """Return the normalised :class:`FieldKind` for this field."""
        if self.repeated:
            return FieldKind.ARRAY
        if self.sub_field:
            return FieldKind.STRUCT
        if self.data_type is None:
            msg = f"Field {self.name!r} has no dataType and no sub_field"
            raise ValueError(msg)
        if self.data_type not in SCALAR_KIND_MAP:
            msg = f"Unsupported Croissant dataType: {self.data_type!r}"
            raise ValueError(msg)
        return SCALAR_KIND_MAP[self.data_type]


class CroissantRecordSetModel(ConfiguredBaseModel):
    """A record set: a logical table of records described by Croissant."""

    id: str | None = Field(default=None, alias=Key.ID.value)
    name: str
    description: str | None = None
    field: list[CroissantFieldModel] = Field(default_factory=list)

    def field_by_name(self, name: str) -> CroissantFieldModel | None:
        """Return the field with the given name, or ``None`` if absent."""
        for f in self.field:
            if f.name == name:
                return f
        return None


class CroissantFileSetModel(ConfiguredBaseModel):
    """A FileSet distribution entry."""

    type: Literal["cr:FileSet"] = Field(alias=Key.TYPE.value)
    id: str = Field(alias=Key.ID.value)
    name: str | None = None
    description: str | None = None
    includes: str
    encoding_format: str | None = None


class CroissantFileObjectModel(ConfiguredBaseModel):
    """A FileObject distribution entry."""

    type: Literal["cr:FileObject"] = Field(alias=Key.TYPE.value)
    id: str = Field(alias=Key.ID.value)
    name: str | None = None
    description: str | None = None
    content_url: str | None = Field(default=None, alias=Key.CONTENT_URL.value)
    encoding_format: str | None = None


class CroissantDatasetModel(ConfiguredBaseModel):
    """Top-level Croissant dataset."""

    name: str | None = None
    description: str | None = None
    record_set: list[CroissantRecordSetModel] = Field(default_factory=list)
    distribution: list[CroissantFileSetModel | CroissantFileObjectModel] = Field(default_factory=list)

    def record_set_by_name(self, name: str) -> CroissantRecordSetModel | None:
        """Return the record set with the given name, or ``None`` if absent."""
        for rs in self.record_set:
            if rs.name == name:
                return rs
        return None


CroissantFieldModel.model_rebuild()
CroissantDatasetModel.model_rebuild()


def load_from_path(path: str | Path) -> CroissantDatasetModel:
    """Load and validate a Croissant JSON-LD file from a local path."""
    return CroissantDatasetModel.model_validate_json(Path(path).read_bytes())


def load_from_url(url: str, timeout: float = 30.0) -> CroissantDatasetModel:
    """Download and validate a Croissant JSON-LD file from an HTTP URL."""
    with urlopen(url, timeout=timeout) as response:  # noqa: S310
        return CroissantDatasetModel.model_validate_json(response.read())
