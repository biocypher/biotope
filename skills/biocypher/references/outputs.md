# Output formats and finalisation

Read this when choosing a backend, configuring `biocypher_config.yaml`, or importing an offline export.

Configuration lives in `biocypher_config.yaml` in the project root or `config/`. Core keys under `biocypher:`:

```yaml
biocypher:
  dbms: neo4j              # neo4j | postgresql | csv | networkx | rdf | …
  schema_config_path: config/schema_config.yaml
  offline: true
  output_directory: biocypher-out
  head_ontology:
    url: https://github.com/biolink/biolink-model/raw/v3.2.1/biolink-model.owl.ttl
    root_node: entity
```

DBMS-specific blocks (`neo4j:`, `postgresql:`, …) hold connection settings and import delimiters.

## Build loop

```python
from biocypher import BioCypher

bc = BioCypher()
bc.write_nodes(node_generator())
bc.write_edges(edge_generator())
bc.write_import_call()      # offline: neo4j-admin script, etc.
bc.write_schema_info()      # optional: schema_info.yaml for NL query tools
```

Repeated `write_nodes` and `write_edges` calls deduplicate within one `BioCypher` instance. `write_schema_info()` runs **after** all nodes and edges are written, and only on offline or in-memory backends. For online Neo4j, install `biocypher[neo4j]`, set `offline: false`, and use `add_*` or driver-backed writes.

## Neo4j offline import

With `dbms: neo4j` and `offline: true`, the output holds `*-header.csv`, `*-part*.csv` and `neo4j-admin-import-call.sh`. Import against a **stopped** database, and read the generated script for the exact `--nodes` and `--relationships` arguments.

```bash
docker run --rm \
  -v "$PWD/biocypher-out:/import" \
  -v neo4j-data:/data \
  neo4j:5-community \
  neo4j-admin database import full neo4j \
    --skip-bad-relationships=true \
    --skip-duplicate-nodes=true \
    --overwrite-destination=true \
    /import/<files from script>
```

**`--skip-bad-relationships` hides id-namespace bugs.** It drops every edge whose endpoint was never written, so the import succeeds and the graph is quietly incomplete. Compare edge counts after importing with it on.

## Other backends

`csv` and tabular output produce plain files for DuckDB, pandas or a custom loader. For `postgresql`, `sqlite`, `arangodb` and `rdf`, see https://biocypher.org/reference/outputs/

## Agent API for small in-memory graphs

Under roughly 100k nodes, `create_workflow()` offers a simpler API with no database export:

```python
from biocypher import create_workflow

kg = create_workflow("my_graph", validation_mode="none")
kg.add_node("TP53", "protein", name="TP53")
kg.add_edge("i1", "interaction", "TP53", "BRAF", confidence=0.8)
kg.save("graph.json")
```

No Neo4j or PostgreSQL export and no streaming ETL. Use `BioCypher()` for production pipelines.
