"""Layer 3: declarative semantic ``mapping.yaml`` and its compiler."""

from biotope.croissant.mapping.compile import (
    CompiledAdapter,
    compile_mapping,
    derive_namespace,
    derive_schema_term,
    iter_entity_tuples,
    iter_relation_tuples,
)
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
from biotope.croissant.mapping.preview import MappingPreview, preview_mapping
from biotope.croissant.mapping.render import (
    build_inspector_appendix,
    render_mapping_with_appendix,
    render_mapping_yaml,
)

__all__ = [
    "CompiledAdapter",
    "DatasetInspection",
    "Endpoint",
    "EntityMapping",
    "ExplodeScan",
    "FieldInfo",
    "Mapping",
    "MappingPreview",
    "RecordSetInfo",
    "RelationMapping",
    "RowScan",
    "Scan",
    "Selector",
    "build_inspector_appendix",
    "compile_mapping",
    "derive_namespace",
    "derive_schema_term",
    "dump_mapping",
    "inspect_dataset",
    "intent_comment",
    "iter_entity_tuples",
    "iter_relation_tuples",
    "load_mapping",
    "preview_mapping",
    "render_inspection_text",
    "render_mapping_with_appendix",
    "render_mapping_yaml",
    "to_snake_case",
    "unresolved_scaffold",
]
