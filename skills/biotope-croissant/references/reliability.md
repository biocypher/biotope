# Mapping reliability

## Bind declared structure

Use the manifest's record-set IDs and fields. A field description establishes
structure, not that every record is readable or every value is valid. Record
partial descriptions and unsupported files as limitations.

If source files change, regenerate directory metadata with `biotope add <directory> --rebake`
or a single file with `biotope add <file> --force`, then review affected mappings. A checksum or timestamp can reveal drift; it does
not assess the meaning of a change.

## Make identity choices explicit

Explain which fields identify entities and which namespaces are intended. The
same entity across sources needs consistent identity semantics. A shared column
name does not prove equivalence, and metadata cannot prove matching values.
Defer uncertain choices for user review. Normalization and project-specific
loaders are later work, not part of this Biotope workflow.

`propose-alignment` generates hypotheses from mapping definitions. Review each
suggestion; do not accept equivalences solely because properties or prefixes
match.

## Preserve research intent

Keep the declared purpose and target entities/relations unless the user changes
them. When a relation lacks support, record the gap and discuss deferral or a
schema change. Never fabricate columns, empty filters or placeholder bindings to
satisfy a slot. Use literal constants only for facts actually known to be fixed.

## State what was checked

`map preview` checks metadata and mapping definitions. Review unresolved slots,
errors and warnings. It does not check source values, transform execution,
identity coverage or graph correctness. Report the checked scope and remaining
scientific choices, then stop at mapping.
