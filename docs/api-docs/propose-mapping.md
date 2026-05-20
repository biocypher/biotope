# `biotope propose-mapping`

Emit a heuristic `mapping.yaml` for a Croissant file: one RecordSet → one node type, FK-shaped fields → edges. The proposal is meant for human (or agent) review before `biotope build` consumes it.

If you run it inside a biotope project, the command now writes to
`mappings/<croissant-stem>.mapping.yaml` automatically. Use `--out` to
override the destination or `--stdout` to print the scaffold instead.

When writing YAML, `biotope propose-mapping` now emits a commented review scaffold:

- key-level guidance for `record_set`, `type`, `id`, `properties`, and `where`
- record-set descriptions pulled from Croissant
- available-field inventories with inferred kinds
- sample rows from the underlying data when the Croissant file points to local files

Use `--preview-rows 0` if you want to suppress sample-row comments.

::: biotope.commands.propose_mapping
