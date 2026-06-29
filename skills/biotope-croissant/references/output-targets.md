# Output targets (biotope boundary)

`biotope build` materialises a BioCypher project and runs it. The **format** of what lands in `build/biocypher-out/` is chosen with:

```bash
biotope build --target {csv,neo4j}   # default: csv
uv run python build/create_knowledge_graph.py
```

Both `build` and `view` print the resolved target — state that format honestly.

## What biotope covers

- **`--target csv`** — node/edge CSVs under `build/biocypher-out/`. Good for inspection, DuckDB, pandas, or custom loading.
- **`--target neo4j`** — bulk-import CSVs plus `neo4j-admin-import-call.sh` in the same directory.

`biotope view` reports node/edge counts, orphaned-edge metrics, and schema diff. Orphaned-edge counts also appear in `build/biocypher-out/build_metrics.json`.

The generated `build/config/biocypher_config.yaml` is **editable** (backend, ontology); `biotope build` only writes it when absent. Do not hand-edit generated adapters or `create_knowledge_graph.py`.

## What is outside biotope (optional)

These are **not required** to finish a biotope project. CSV output alone may be enough. Before doing any of the below, **ask the user** whether they want to continue — do not assume Neo4j import, standalone BioCypher tuning, or natural-language querying.

| User goal | Load skill |
|-----------|------------|
| Tune BioCypher backends, adapters, schema config, Neo4j import details, `write_schema_info()` | **biocypher** — see `references/outputs.md` and `references/schema-config.md` in that skill |
| Query a loaded graph in natural language | **biochatter** — needs `schema_info.yaml` and a running graph DB |

If the user declines, stop after `biotope view` confirms non-empty outputs for their chosen `--target`.
