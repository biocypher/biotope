"""Layer 3: declarative semantic ``mapping.yaml`` definitions and metadata checks."""

from biotope.croissant.mapping.defaults import intent_comment, unresolved_scaffold
from biotope.croissant.mapping.inspector import (
    DatasetInspection,
    FieldInfo,
    RecordSetInfo,
    inspect_dataset,
    render_inspection_text,
)
from biotope.croissant.mapping.loader import dump_mapping, load_mapping
from biotope.croissant.mapping.model import (
    Endpoint,
    EntityMapping,
    ExplodeScan,
    Mapping,
    RelationMapping,
    RowScan,
    Scan,
    Selector,
    to_snake_case,
)
from biotope.croissant.mapping.preview import (
    AggregatedEntity,
    AggregatedRelation,
    MappingPreview,
    MultiMappingPreview,
    aggregate_previews,
    preview_mapping,
)
from biotope.croissant.mapping.render import (
    build_inspector_appendix,
    render_mapping_with_appendix,
    render_mapping_yaml,
)

__all__ = [
    "AggregatedEntity",
    "AggregatedRelation",
    "DatasetInspection",
    "Endpoint",
    "EntityMapping",
    "ExplodeScan",
    "FieldInfo",
    "Mapping",
    "MappingPreview",
    "MultiMappingPreview",
    "RecordSetInfo",
    "RelationMapping",
    "RowScan",
    "Scan",
    "Selector",
    "aggregate_previews",
    "build_inspector_appendix",
    "dump_mapping",
    "inspect_dataset",
    "intent_comment",
    "load_mapping",
    "preview_mapping",
    "render_inspection_text",
    "render_mapping_with_appendix",
    "render_mapping_yaml",
    "to_snake_case",
    "unresolved_scaffold",
]
