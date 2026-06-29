# Output formats and finalisation

Configure via `biocypher_config.yaml` (project root or `config/`). Core keys under `biocypher:`:

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

DBMS-specific blocks (`neo4j:`, `postgresql:`, …) hold connection and import delimiter settings.

## Build loop

```python
from biocypher import BioCypher

bc = BioCypher()
bc.write_nodes(node_generator())
bc.write_edges(edge_generator())
bc.write_import_call()      # offline: neo4j-admin script, etc.
bc.write_schema_info()      # optional: schema_info.yaml for NL query tools
```

- Multiple `write_nodes` / `write_edges` calls deduplicate within one `BioCypher` instance.
- `write_schema_info()` must run **after** all nodes and edges are written (offline or in-memory backends only).
- Online Neo4j: `pip install "biocypher[neo4j]"`, set `offline: false`, use `add_*` or driver-backed writes per docs.

## Neo4j offline import

With `dbms: neo4j` and `offline: true`, output includes `*-header.csv`, `*-part*.csv`, and `neo4j-admin-import-call.sh`. Run import against a **stopped** database; read the generated script for exact `--nodes` / `--relationships` args.

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

`--skip-bad-relationships` drops edges with missing endpoints — convenient but masks id-namespace bugs. Verify edge counts after import.

## Other backends

- **csv / tabular** — plain files for DuckDB, pandas, custom loaders.
- **postgresql / sqlite / arangodb / rdf** — see https://biocypher.org/reference/outputs/

## Agent API (small in-memory graphs)

For prototyping (<100k nodes), `create_workflow()` offers a simpler API without database export:

```python
from biocypher import create_workflow

kg = create_workflow("my_graph", validation_mode="none")
kg.add_node("TP53", "protein", name="TP53")
kg.add_edge("i1", "interaction", "TP53", "BRAF", confidence=0.8)
kg.save("graph.json")
```

No Neo4j/PostgreSQL export, no streaming ETL — use legacy `BioCypher()` for production pipelines.

## Optional next step

With `schema_info.yaml` and a loaded graph DB, natural-language querying is the **biochatter** skill — ask the user before loading it.
